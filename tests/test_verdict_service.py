from evidence_root.schemas import Claim, ClaimScore
from evidence_root.services.causal_reasoner import CausalAssessment
from evidence_root.services.comparison_counter import ComparisonEstimate
from evidence_root.services.verdict_service import decide_verdict


def _empty_score(claim_id="C1"):
    return ClaimScore(claim_id=claim_id)


def _claim():
    return Claim(
        claim_id="C1", claim_text="A가 B보다 더 관심받았다", claim_type="comparison",
        checkability="partially_checkable", entities=["A", "B"],
    )


def test_comparison_estimate_upgrades_insufficient_when_clear_gap():
    estimate = ComparisonEstimate(entity_a="A", count_a=1000, entity_b="B", count_b=100)
    verdict = decide_verdict(_claim(), _empty_score(), estimate)
    assert verdict.status.value == "partially_supported"
    assert any("언급량" in p for p in verdict.confirmed_points)


def test_comparison_estimate_flips_when_reverse_gap():
    estimate = ComparisonEstimate(entity_a="A", count_a=50, entity_b="B", count_b=900)
    verdict = decide_verdict(_claim(), _empty_score(), estimate)
    assert verdict.status.value == "likely_false"


def test_comparison_estimate_stays_mixed_when_close():
    estimate = ComparisonEstimate(entity_a="A", count_a=100, entity_b="B", count_b=110)
    verdict = decide_verdict(_claim(), _empty_score(), estimate)
    assert verdict.status.value == "mixed"


def test_without_comparison_estimate_falls_back_to_insufficient():
    verdict = decide_verdict(_claim(), _empty_score(), None)
    assert verdict.status.value == "insufficient_evidence"


def test_comparison_estimate_wins_over_noisy_own_evidence_conflict():
    """비교 주장 자체를 검색했을 때 잡음 섞인 결과로 상충(source_conflict)이 높게 나와도, 훨씬 신뢰도
    높은 '검증된 독립 근거 수 비교'가 명확한 차이를 보이면 그걸 최종 판정 기준으로 써야 한다."""
    noisy_score = ClaimScore(
        claim_id="C1", independent_support_count=1, independent_refute_count=1,
        support_strength=0.5, refute_strength=0.5, source_conflict=0.5,
    )
    estimate = ComparisonEstimate(entity_a="늑구", count_a=8, entity_b="예비군", count_b=5, basis="검증된 독립 근거 수")
    verdict = decide_verdict(_claim(), noisy_score, estimate)
    assert verdict.status.value == "partially_supported"


def _causal_claim():
    return Claim(
        claim_id="C3", claim_text="A가 B에 영향을 줬다", claim_type="causal",
        checkability="partially_checkable", entities=["A", "B"],
    )


def test_causal_claim_with_unconfirmed_premises_becomes_unverifiable():
    """전제가 되는 개별 사건이 확인되지 않았다면(가짜 정보 등), 인과관계는 '부분적으로 지지됨'이 아니라
    '판단 불가'로 나와야 한다 — 근거 없는 사건들 사이의 인과관계를 지지된 것처럼 보이면 안 된다."""
    assessment = CausalAssessment(reasoning="전제 사건이 확인되지 않았습니다.", plausible=None, premises_confirmed=False)
    verdict = decide_verdict(_causal_claim(), _empty_score(), None, assessment)
    assert verdict.status.value == "unverifiable"


def test_causal_claim_with_confirmed_premises_and_plausible_interpretation():
    assessment = CausalAssessment(reasoning="두 사건 시점상 연결이 합리적입니다.", plausible=True, premises_confirmed=True)
    verdict = decide_verdict(_causal_claim(), _empty_score(), None, assessment)
    assert verdict.status.value == "partially_supported"
    assert any("해석" in p for p in verdict.confirmed_points)
