"""설정된 검색 Provider만 사용해 주장별 원시 검색 결과를 수집한다. 한 Provider가 실패해도 계속 진행."""
from __future__ import annotations

import logging

from ..providers.base import RawSearchResult
from ..schemas import Claim, Evidence, SourceType
from ..utils.http_client import run_concurrently

logger = logging.getLogger("evidence_root.services.evidence_search")

_SOURCE_TYPE_BY_PROVIDER = {
    "naver_news": SourceType.news_report,
    "naver_web": SourceType.unknown,
    "naver_blog": SourceType.blog,
    "naver_cafe": SourceType.community,
    "google_factcheck": SourceType.fact_check,
}


def collect_raw_results(
    claim: Claim,
    queries: list[str],
    providers: list,
    results_per_query: int,
    max_raw_results: int,
    process_log: dict,
) -> list[Evidence]:
    all_results: list[RawSearchResult] = []
    provider_counts: dict[str, int] = {}

    def _run_provider_query(pair):
        provider, query = pair
        try:
            return provider.search(query, results_per_query)
        except Exception as exc:
            logger.warning("provider=%s query=%s 실패: %s", provider.provider_name, query, exc)
            return []

    pairs = [(p, q) for p in providers if p.is_configured() for q in queries]
    outputs = run_concurrently(_run_provider_query, pairs)

    for (provider, _query), output in zip(pairs, outputs):
        if not output:
            continue
        provider_counts[provider.provider_name] = provider_counts.get(provider.provider_name, 0) + len(output)
        all_results.extend(output)

    process_log.setdefault("search_counts", {})[claim.claim_id] = provider_counts

    seen_urls: set[str] = set()
    evidences: list[Evidence] = []
    for idx, raw in enumerate(all_results):
        if not raw.url or raw.url in seen_urls:
            continue
        seen_urls.add(raw.url)
        evidences.append(
            Evidence(
                evidence_id=f"{claim.claim_id}-E{idx + 1}",
                claim_id=claim.claim_id,
                url=raw.url,
                title=raw.title,
                publisher=raw.publisher,
                published_at=raw.published_at,
                snippet=raw.snippet,
                source_type=_SOURCE_TYPE_BY_PROVIDER.get(raw.search_provider, SourceType.unknown),
                search_provider=raw.search_provider,
            )
        )
        if len(evidences) >= max_raw_results:
            break

    return evidences
