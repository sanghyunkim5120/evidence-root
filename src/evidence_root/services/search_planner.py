"""주장별 검색어를 동적으로 생성한다 (스펙 10장). 사건명/기관명 하드코딩 없음 — claim 필드에서 파생."""
from __future__ import annotations

from ..schemas import Claim

TARGET_QUERY_COUNT = 4


def build_queries(claim: Claim) -> list[str]:
    target = TARGET_QUERY_COUNT
    keywords = " ".join(claim.keywords[:5]) or claim.claim_text[:40]
    orgs = claim.organizations
    dates = " ".join(claim.dates[:2])
    locations = " ".join(claim.locations[:2])

    candidates: list[str] = []
    candidates.append(keywords)  # core_event
    if claim.claim_type == "quote" and claim.claim_text:
        candidates.append(f'"{claim.claim_text[:60]}"')  # exact_phrase
    if orgs:
        candidates.append(f"{orgs[0]} 공식 발표 {keywords}")
    candidates.append(f"{keywords} 보도")  # independent_news
    candidates.append(f"{keywords} 반박 OR 정정 OR 해명")
    candidates.append(f"{keywords} 팩트체크")
    if dates or locations:
        candidates.append(f"{keywords} {dates} {locations}".strip())
    if claim.quantities:
        candidates.append(f"{keywords} {claim.quantities[0]} 통계 원자료")
    if len(candidates) < target and claim.entities:
        candidates.append(f"{claim.entities[0]} {keywords}")

    seen: list[str] = []
    for c in candidates:
        c = " ".join(c.split())
        if c and c not in seen:
            seen.append(c)
    return seen[:target]


def expand_query_once(query: str) -> str:
    """검색 결과가 부족할 때 짧게 바꿔 한 번만 확장 검색한다."""
    words = query.split()
    if len(words) <= 2:
        return query
    return " ".join(words[:2])
