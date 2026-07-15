"""전체 분석 파이프라인 오케스트레이션 (스펙 8장 순서)."""
from __future__ import annotations

import logging
from typing import Callable

from ..provider_registry import ProviderRegistry
from ..schemas import AnalysisResult, ClaimVerdict, Evidence, StanceResult
from . import (
    causal_reasoner,
    claim_extractor,
    comparison_counter,
    deduplicator,
    document_fetcher,
    evidence_search,
    followup_generator,
    official_source_resolver,
    provenance_analyzer,
    relevance_filter,
    scoring_service,
    search_planner,
    stance_analyzer,
    summary_generator,
    verdict_service,
)

logger = logging.getLogger("evidence_root.services.analysis_pipeline")

MODE_LIMITS = {
    "fast": {"results_per_query": 10, "max_raw_results": 40, "max_fetched_documents": 20, "max_final_evidence": 8},
    "thorough": {"results_per_query": 20, "max_raw_results": 120, "max_fetched_documents": 50, "max_final_evidence": 15},
}


def run_pipeline(
    input_text: str,
    registry: ProviderRegistry,
    mode: str = "thorough",
    on_step: Callable[[str], None] | None = None,
) -> AnalysisResult:
    def step(name: str) -> None:
        logger.info("파이프라인 단계: %s", name)
        if on_step:
            on_step(name)

    limits = MODE_LIMITS.get(mode, MODE_LIMITS["thorough"])
    process_log: dict = {"mode": mode}
    llm = registry.text_llm()

    step("주장 추출")
    claims = claim_extractor.extract_claims(input_text, llm)
    process_log["claim_count"] = len(claims)

    all_evidences: list[Evidence] = []
    all_stances: list[StanceResult] = []
    all_edges = []
    all_verdicts: list[ClaimVerdict] = []
    evidence_by_claim_id: dict[str, list[Evidence]] = {}
    stances_by_claim_id: dict[str, list[StanceResult]] = {}

    step("검색 계획")
    for claim in claims:
        queries = search_planner.build_queries(claim, mode)
        process_log.setdefault("queries", {})[claim.claim_id] = queries

        step("공식 자료 확인")
        official_candidates = official_source_resolver.resolve_official_sources(claim, llm)
        process_log.setdefault("official_candidates", {})[claim.claim_id] = official_candidates

        step("자료 검색")
        raw_evidences = evidence_search.collect_raw_results(
            claim,
            queries,
            registry.search_providers(),
            limits["results_per_query"],
            limits["max_raw_results"],
            process_log,
        )

        step("본문 수집")
        fetch_targets = raw_evidences[: limits["max_fetched_documents"]]
        docs = document_fetcher.fetch_documents([e.url for e in fetch_targets])
        fetched_ok = 0
        for e in fetch_targets:
            doc = docs.get(e.url)
            if doc and doc.body_text:
                e.body_text = doc.body_text
                e.full_text_available = True
                e.publisher = e.publisher or doc.publisher
                e.author = doc.author
                e.published_at = e.published_at or doc.published_at
                e.canonical_url = doc.canonical_url or e.url
                e.outbound_links = doc.outbound_links[:20]
                e.image_urls = doc.image_urls
                fetched_ok += 1
            else:
                e.canonical_url = e.url
        process_log.setdefault("body_fetch_failures", {})[claim.claim_id] = len(fetch_targets) - fetched_ok

        pre_relevance_count = len(fetch_targets)
        relevant = relevance_filter.prefilter_relevance(claim, fetch_targets, threshold=0.2)
        relevant = relevance_filter.gemini_relevance_check(claim, relevant, llm)
        process_log.setdefault("relevance_excluded", {})[claim.claim_id] = pre_relevance_count - len(relevant)

        step("중복·원출처 분석")
        relevant = deduplicator.deduplicate(relevant)
        edges = provenance_analyzer.analyze_provenance(relevant)
        all_edges.extend(edges)

        relevant = relevant[: limits["max_final_evidence"]]

        step("교차검증")
        claim_stances = stance_analyzer.analyze_stances(claim, relevant, llm)

        all_evidences.extend(relevant)
        all_stances.extend(claim_stances)
        evidence_by_claim_id[claim.claim_id] = relevant
        stances_by_claim_id[claim.claim_id] = claim_stances

    step("결과 생성")
    verdicts_by_claim_id: dict[str, ClaimVerdict] = {}
    # 인과관계 주장은 전제가 되는 개별 사실 주장의 판정이 먼저 나와 있어야 해석할 수 있으므로 뒤로 미룬다.
    ordered_claims = [c for c in claims if c.claim_type != "causal"] + [c for c in claims if c.claim_type == "causal"]

    for claim in ordered_claims:
        relevant = evidence_by_claim_id.get(claim.claim_id, [])
        claim_stances = stances_by_claim_id.get(claim.claim_id, [])
        score = scoring_service.compute_score(claim, relevant, claim_stances)

        # 비교 주장은 우선 같은 입력에서 나온 개별 사실 확인 주장의 (이미 검증된) 독립 근거 수로 비교하고,
        # 대응하는 개별 주장을 찾지 못했을 때만 네이버 전체 언급량 근사치로 대체한다.
        comparison_estimate = comparison_counter.estimate_comparison_from_evidence(claim, claims, evidence_by_claim_id)
        if comparison_estimate is None:
            comparison_estimate = comparison_counter.estimate_comparison(claim, registry.get("naver_news"), claims)
        if comparison_estimate is not None:
            process_log.setdefault("comparison_estimates", {})[claim.claim_id] = {
                "entity_a": comparison_estimate.entity_a,
                "count_a": comparison_estimate.count_a,
                "entity_b": comparison_estimate.entity_b,
                "count_b": comparison_estimate.count_b,
                "basis": comparison_estimate.basis,
            }

        # 인과관계 주장은 기사에서 직접 확인되지 않는 경우가 많아, 전제 사실(위에서 먼저 판정된 개별
        # 사건 주장)을 바탕으로 한 LLM 해석으로 보완한다.
        causal_assessment = causal_reasoner.evaluate_causal_claim(claim, claims, verdicts_by_claim_id, llm)
        if causal_assessment is not None:
            process_log.setdefault("causal_assessments", {})[claim.claim_id] = {
                "reasoning": causal_assessment.reasoning,
                "plausible": causal_assessment.plausible,
                "premises_confirmed": causal_assessment.premises_confirmed,
            }

        verdict = verdict_service.decide_verdict(claim, score, comparison_estimate, causal_assessment)
        verdicts_by_claim_id[claim.claim_id] = verdict
        all_verdicts.append(verdict)

    claim_order = {c.claim_id: idx for idx, c in enumerate(claims)}
    all_verdicts.sort(key=lambda v: claim_order.get(v.claim_id, 0))

    overall_summary = summary_generator.generate_summary(all_verdicts, llm)
    followups = followup_generator.generate_followups(all_verdicts, llm)

    return AnalysisResult(
        input_summary=input_text[:300],
        claims=claims,
        evidences=all_evidences,
        stances=all_stances,
        provenance_edges=all_edges,
        verdicts=all_verdicts,
        overall_summary=overall_summary,
        followup_questions=followups,
        process_log=process_log,
    )
