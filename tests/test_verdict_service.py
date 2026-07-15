from evidence_root.schemas import Claim, ClaimScore
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
