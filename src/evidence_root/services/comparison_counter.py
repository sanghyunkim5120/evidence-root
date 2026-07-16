"""'A가 B보다 더 관심을 받았다' 류의 비교 주장을, 네이버 뉴스 언급량(검색 결과 총 건수)을 근사 지표로
활용해 판단한다. 정확한 관심도 측정은 아니지만, 근거가 전혀 없는 것보다는 훨씬 구체적인 판단 재료가 된다."""
from __future__ import annotations

from dataclasses import dataclass

from ..providers.naver_news_provider import NaverNewsSearchProvider
from ..schemas import Claim


@dataclass
class ComparisonEstimate:
    entity_a: str
    count_a: int
    entity_b: str
    count_b: int
    basis: str = "네이버 뉴스 전체 언급량"

    @property
    def ratio_label(self) -> str:
        if self.count_a == 0 and self.count_b == 0:
            return f"두 대상 모두 {self.basis}을 확인할 수 없습니다."
        larger, smaller = (self.entity_a, self.entity_b) if self.count_a >= self.count_b else (self.entity_b, self.entity_a)
        return f"'{larger}'의 {self.basis}이 '{smaller}'보다 많습니다."


def _narrow_query(entity: str, claims: list[Claim]) -> str:
    """짧은 대상명만으로 검색하면 다른 시기·다른 장소의 동명 사건까지 섞여 건수가 부풀려진다.
    비교 주장 자신뿐 아니라, 같은 입력에서 나온 다른 세부 주장(개별 사건 사실 확인용)에 더 구체적인
    날짜/장소가 뽑혀 있는 경우가 많아 그것도 함께 참고해 검색어를 좁힌다."""
    dates = [d for c in claims for d in c.dates]
    locations = [l for c in claims for l in c.locations]
    extra = dates[:1] + locations[:1]
    if not extra:
        return entity
    return f"{entity} {' '.join(extra)}"


def estimate_comparison(
    claim: Claim, naver_news: NaverNewsSearchProvider, sibling_claims: list[Claim] | None = None
) -> ComparisonEstimate | None:
    if claim.claim_type != "comparison" or len(claim.entities) < 2:
        return None
    if not naver_news.is_configured():
        return None

    context_claims = sibling_claims if sibling_claims is not None else [claim]
    entity_a, entity_b = claim.entities[0], claim.entities[1]
    count_a = naver_news.get_total_count(_narrow_query(entity_a, context_claims))
    count_b = naver_news.get_total_count(_narrow_query(entity_b, context_claims))
    if count_a is None or count_b is None:
        return None

    return ComparisonEstimate(entity_a=entity_a, count_a=count_a, entity_b=entity_b, count_b=count_b)


def _find_sibling_claim(entity: str, claims: list[Claim], exclude_id: str) -> Claim | None:
    """entity(예: "늑구 탈출")가 형제 주장 문장에 토씨 하나 안 틀리고 그대로 들어있는 경우만 찾으면,
    한국어 조사("늑구가", "늑구는" 등)나 어순 차이 때문에 거의 항상 매칭에 실패한다. 대신 entity를
    단어 단위로 쪼개서 각 단어가 부분 문자열로 등장하는지 세고, 가장 많이 겹치는 형제 주장을 고른다."""
    entity_words = [w for w in entity.split() if len(w) >= 2] or [entity]

    best_claim: Claim | None = None
    best_score = 0
    for c in claims:
        if c.claim_id == exclude_id or c.claim_type == "comparison":
            continue
        haystack = " ".join([c.claim_text, *c.entities, *c.keywords])
        score = sum(1 for w in entity_words if w in haystack)
        if score > best_score:
            best_score = score
            best_claim = c
    return best_claim


def estimate_comparison_from_evidence(
    claim: Claim, claims: list[Claim], evidence_by_claim_id: dict[str, list]
) -> ComparisonEstimate | None:
    """비교 주장의 두 대상 각각에 대응하는 개별 사실 확인 주장(event 등)을 찾아, 그 주장에서 실제로
    검색·관련성 필터·중복제거까지 거친 독립 근거 수를 비교 지표로 쓴다. 원문 그대로 네이버 전체
    건수를 세는 것보다 노이즈(다른 시기·다른 사건 혼입)가 훨씬 적다."""
    if claim.claim_type != "comparison" or len(claim.entities) < 2:
        return None

    entity_a, entity_b = claim.entities[0], claim.entities[1]
    claim_a = _find_sibling_claim(entity_a, claims, claim.claim_id)
    claim_b = _find_sibling_claim(entity_b, claims, claim.claim_id)
    if claim_a is None or claim_b is None or claim_a.claim_id == claim_b.claim_id:
        return None

    count_a = len({e.duplicate_cluster_id or e.evidence_id for e in evidence_by_claim_id.get(claim_a.claim_id, [])})
    count_b = len({e.duplicate_cluster_id or e.evidence_id for e in evidence_by_claim_id.get(claim_b.claim_id, [])})
    return ComparisonEstimate(
        entity_a=entity_a, count_a=count_a, entity_b=entity_b, count_b=count_b, basis="검증된 독립 근거 수"
    )
