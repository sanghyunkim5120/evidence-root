"""관련성 필터링: 1차 TF-IDF/RapidFuzz/키워드 일치, 2차 LLM 평가 (스펙 14장)."""
from __future__ import annotations

import logging

from ..providers.base import TextLLMProvider
from ..schemas import Claim, Evidence

logger = logging.getLogger("evidence_root.services.relevance_filter")


def _text_of(evidence: Evidence) -> str:
    return " ".join(filter(None, [evidence.title, evidence.snippet, evidence.body_text[:1000]]))


def prefilter_relevance(claim: Claim, evidences: list[Evidence], threshold: float) -> list[Evidence]:
    """TF-IDF 코사인 유사도 + 키워드/날짜 일치로 1차 필터링."""
    if not evidences:
        return []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        claim_text = claim.claim_text + " " + " ".join(claim.keywords)
        corpus = [claim_text] + [_text_of(e) for e in evidences]
        vectorizer = TfidfVectorizer(max_features=4000)
        matrix = vectorizer.fit_transform(corpus)
        sims = cosine_similarity(matrix[0:1], matrix[1:])[0]
    except Exception as exc:
        logger.warning("TF-IDF 계산 실패, RapidFuzz만 사용: %s", exc)
        sims = [0.0] * len(evidences)

    from rapidfuzz import fuzz

    kept: list[Evidence] = []
    core_keywords = [kw for kw in claim.keywords[:3] if kw]
    for evidence, sim in zip(evidences, sims):
        fuzzy = fuzz.token_set_ratio(claim.claim_text, _text_of(evidence)) / 100.0
        # 흔한 단어 하나만 겹쳐도 통과시키면 완전히 다른 주제가 새어 들어온다. 핵심 키워드 중
        # "과반수"가 실제로 등장할 때만 키워드 일치 보너스를 준다.
        matched_keywords = sum(1 for kw in core_keywords if kw in _text_of(evidence))
        keyword_hit = bool(core_keywords) and matched_keywords >= max(1, (len(core_keywords) + 1) // 2)
        score = max(sim, fuzzy * 0.8) + (0.1 if keyword_hit else 0.0)
        evidence.relevance_score = round(float(score), 4)
        if score >= threshold:
            kept.append(evidence)
    return kept


BATCH_PROMPT_TEMPLATE = """다음 주장과 자료 목록을 보고 각 자료가 실제로 관련있는지 엄격하게 평가하라.
같은 단어(인물명/장소명/일반명사)가 겹쳐도 다루는 사건·시점·맥락이 다르면 반드시 false로 판단하라.
동명이인, 다른 사건, 다른 지역/기간의 통계, 같은 주제의 일반적인 배경 설명(이 사건을 직접 다루지 않는
기사)은 전부 관련 없음(false)이다. 조금이라도 확신이 안 서면 false로 판단하라 — 애매하면 포함시키지 마라.

주장: {claim_text}

자료 목록:
{items}

각 자료의 id에 대해 JSON 배열로만 응답하라:
[{{"id": "E1", "relevant": true/false}}, ...]
"""


def gemini_relevance_check(claim: Claim, evidences: list[Evidence], gemini: TextLLMProvider) -> list[Evidence]:
    """2차 LLM 평가. 미설정 시, 또는 이 항목에 대한 평가를 못 받았을 때는 1차 필터의 판단(통과)을
    신뢰한다.

    한때는 평가에 실패한 자료를 전부 제외했는데, 1차 필터(TF-IDF+키워드 과반수 일치)가 이미 꽤
    정확한 상태에서 API가 자주 실패/응답잘림(rate limit)이 나는 날엔 오히려 진짜 관련 있는 자료까지
    싹 다 "근거 부족"으로 날려버리는 부작용이 더 컸다. 그래서 2차 평가가 명확히 "관련 없음"이라고
    응답한 자료만 제외하고, 평가 자체를 못 받은 자료는 1차 필터 통과 상태를 그대로 유지한다.
    """
    if not gemini.is_configured() or not evidences:
        return evidences

    relevant_map: dict[str, bool] = {}
    chunk_size = 4
    for i in range(0, len(evidences), chunk_size):
        chunk = evidences[i : i + chunk_size]
        items = "\n\n".join(
            f"id: {e.evidence_id}\n제목: {e.title}\n내용: {(e.body_text or e.snippet)[:400]}" for e in chunk
        )
        raw = gemini.generate_json(BATCH_PROMPT_TEMPLATE.format(claim_text=claim.claim_text, items=items))
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("id"):
                    relevant_map[item["id"]] = item.get("relevant", True)
        else:
            logger.warning("관련성 평가 실패, 이 묶음(%d개)은 1차 필터 결과를 그대로 유지", len(chunk))

    return [e for e in evidences if relevant_map.get(e.evidence_id, True) is not False]
