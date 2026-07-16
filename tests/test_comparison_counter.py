from evidence_root.schemas import Claim, Evidence
from evidence_root.services.comparison_counter import estimate_comparison, estimate_comparison_from_evidence


class FakeNaverNews:
    def __init__(self, counts):
        self._counts = counts

    def is_configured(self):
        return True

    def get_total_count(self, query):
        return self._counts.get(query)


def test_estimate_comparison_returns_none_for_non_comparison_claim():
    claim = Claim(claim_id="C1", claim_text="사건이 있었다", claim_type="event", checkability="checkable", entities=["A", "B"])
    assert estimate_comparison(claim, FakeNaverNews({})) is None


def test_estimate_comparison_returns_none_without_two_entities():
    claim = Claim(claim_id="C1", claim_text="A가 더 관심받았다", claim_type="comparison", checkability="partially_checkable", entities=["A"])
    assert estimate_comparison(claim, FakeNaverNews({})) is None


def test_estimate_comparison_computes_counts():
    claim = Claim(
        claim_id="C1", claim_text="A가 B보다 더 관심받았다", claim_type="comparison",
        checkability="partially_checkable", entities=["A", "B"],
    )
    naver = FakeNaverNews({"A": 500, "B": 100})
    result = estimate_comparison(claim, naver)
    assert result.count_a == 500
    assert result.count_b == 100
    assert "A" in result.ratio_label


def test_estimate_comparison_narrows_query_using_sibling_claim_dates():
    """비교 주장 자체엔 날짜가 없어도, 같이 추출된 개별 사건 주장에 날짜가 있으면 빌려와서 검색을 좁힌다."""
    comparison_claim = Claim(
        claim_id="C3", claim_text="A가 B보다 더 관심받았다", claim_type="comparison",
        checkability="partially_checkable", entities=["A", "B"],
    )
    sibling_with_date = Claim(
        claim_id="C1", claim_text="A 사건이 있었다", claim_type="event", checkability="checkable",
        dates=["2026년 3월"],
    )
    naver = FakeNaverNews({"A 2026년 3월": 30, "B 2026년 3월": 200})
    result = estimate_comparison(comparison_claim, naver, [comparison_claim, sibling_with_date])
    assert result.count_a == 30
    assert result.count_b == 200


def _evidence(idx, claim_id, cluster):
    return Evidence(evidence_id=f"E{idx}", claim_id=claim_id, url=f"https://x.com/{idx}", duplicate_cluster_id=cluster)


def test_estimate_comparison_from_evidence_uses_sibling_independent_counts():
    comparison_claim = Claim(
        claim_id="C3", claim_text="늑대 탈출이 예비군 사망사건보다 더 관심받았다", claim_type="comparison",
        checkability="partially_checkable", entities=["늑대 탈출", "예비군 사망사건"],
    )
    wolf_claim = Claim(claim_id="C1", claim_text="늑대 탈출이 있었다", claim_type="event", checkability="checkable")
    reservist_claim = Claim(claim_id="C2", claim_text="예비군 사망사건이 있었다", claim_type="event", checkability="checkable")
    claims = [comparison_claim, wolf_claim, reservist_claim]

    evidence_by_claim_id = {
        "C1": [_evidence(1, "C1", "cluster-a"), _evidence(2, "C1", "cluster-b")],  # 독립 근거 2개
        "C2": [
            _evidence(3, "C2", "cluster-c"),
            _evidence(4, "C2", "cluster-d"),
            _evidence(5, "C2", "cluster-e"),
            _evidence(6, "C2", "cluster-f"),
            _evidence(7, "C2", "cluster-g"),
            _evidence(8, "C2", "cluster-h"),
        ],  # 독립 근거 6개
    }

    result = estimate_comparison_from_evidence(comparison_claim, claims, evidence_by_claim_id)
    assert result.count_a == 2
    assert result.count_b == 6
    assert result.basis == "검증된 독립 근거 수"


def test_estimate_comparison_from_evidence_matches_despite_korean_particles():
    """entity가 "늑구 탈출"이어도, 형제 주장 문장엔 조사가 붙어 "늑구가 ... 탈출한 사건이 있었다"처럼
    나온다 — 토씨 하나 안 틀리는 완전 일치가 아니라 단어 단위 부분 일치로 찾아야 한다."""
    comparison_claim = Claim(
        claim_id="C3", claim_text="늑구 탈출이 예비군 사망사건보다 더 관심받았다", claim_type="comparison",
        checkability="partially_checkable", entities=["늑구 탈출", "예비군 사망사건"],
    )
    wolf_claim = Claim(
        claim_id="C1", claim_text="늑구가 동물원에서 탈출한 사건이 실제로 있었다",
        claim_type="event", checkability="checkable",
    )
    reservist_claim = Claim(
        claim_id="C2", claim_text="예비군이 훈련 도중 사망한 사건이 실제로 있었다",
        claim_type="event", checkability="checkable",
    )
    claims = [comparison_claim, wolf_claim, reservist_claim]

    evidence_by_claim_id = {
        "C1": [_evidence(1, "C1", "cluster-a"), _evidence(2, "C1", "cluster-b"), _evidence(3, "C1", "cluster-c")],
        "C2": [_evidence(4, "C2", "cluster-d")],
    }

    result = estimate_comparison_from_evidence(comparison_claim, claims, evidence_by_claim_id)
    assert result is not None
    assert result.count_a == 3
    assert result.count_b == 1


def test_estimate_comparison_from_evidence_returns_none_without_sibling_claims():
    comparison_claim = Claim(
        claim_id="C1", claim_text="A가 B보다 더 관심받았다", claim_type="comparison",
        checkability="partially_checkable", entities=["A", "B"],
    )
    result = estimate_comparison_from_evidence(comparison_claim, [comparison_claim], {})
    assert result is None
