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


def test_comparison_estimate_used_only_when_no_direct_evidence_found():
    """비교 주장 자체를 검색했는데 아무 직접 근거도 못 찾았을 때만(독립 지지/반박 둘 다 0건) 근사
    지표(검증된 독립 근거 수 비교)를 최종 판단 기준으로 쓴다."""
    estimate = ComparisonEstimate(entity_a="늑구", count_a=8, entity_b="예비군", count_b=5, basis="검증된 독립 근거 수")
    verdict = decide_verdict(_claim(), _empty_score(), estimate)
    assert verdict.status.value == "partially_supported"


def test_direct_evidence_overrides_comparison_estimate_when_both_available():
    """비교 주장에 대해 실제로 검색된 직접 근거(예: "B가 A보다 더 관심받았다"를 다룬 기사)가 있으면,
    근사 지표(근거 수 비교)보다 그 실제 자료를 우선해서 판정에 반영해야 한다."""
    direct_evidence_score = ClaimScore(
        claim_id="C1", independent_support_count=0, independent_refute_count=2,
        support_strength=0.0, refute_strength=0.9, source_conflict=0.0,
    )
    estimate = ComparisonEstimate(entity_a="늑구", count_a=8, entity_b="예비군", count_b=5, basis="검증된 독립 근거 수")
    verdict = decide_verdict(_claim(), direct_evidence_score, estimate)
    # 근사 지표는 "늑구가 더 관심받았다"를 지지하지만, 실제 자료가 이를 반박했으므로 반박 쪽으로 나와야 한다
    assert verdict.status.value == "likely_false"
    # 근사 지표도 참고 정보로는 계속 표시된다
    assert any("언급량" in p or "근거 수" in p for p in verdict.confirmed_points)


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
