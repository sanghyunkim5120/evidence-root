"""점수를 8단계 판정 상태로 매핑한다 (스펙 17장). 신뢰도는 절대적 진실 확률이 아님을 UI에서 함께 표시한다."""
from __future__ import annotations

from ..schemas import Checkability, Claim, ClaimScore, ClaimVerdict, VerdictStatus
from .comparison_counter import ComparisonEstimate

_COMPARISON_MARGIN = 1.3  # 이 배율 이상 차이나야 유의미한 우열로 본다


def decide_verdict(
    claim: Claim, score: ClaimScore, comparison_estimate: ComparisonEstimate | None = None
) -> ClaimVerdict:
    if claim.checkability in (Checkability.opinion, Checkability.unverifiable):
        status = VerdictStatus.unverifiable
    elif score.independent_support_count == 0 and score.independent_refute_count == 0:
        status = VerdictStatus.insufficient_evidence
    elif score.source_conflict >= 0.4:
        status = VerdictStatus.mixed
    elif score.independent_refute_count >= 3 and score.refute_strength >= 0.85 and score.source_conflict < 0.1:
        status = VerdictStatus.false
    elif score.independent_refute_count >= 2 and score.refute_strength >= 0.65:
        status = VerdictStatus.likely_false
    elif score.independent_support_count >= 3 and score.support_strength >= 0.85 and score.source_conflict < 0.1:
        status = VerdictStatus.confirmed
    elif score.independent_support_count >= 2 and score.support_strength >= 0.65:
        status = VerdictStatus.likely_true
    elif score.independent_support_count >= 1 and score.support_strength >= 0.45:
        status = VerdictStatus.partially_supported
    else:
        status = VerdictStatus.insufficient_evidence

    if comparison_estimate is not None and status == VerdictStatus.insufficient_evidence:
        if comparison_estimate.count_a > comparison_estimate.count_b * _COMPARISON_MARGIN:
            status = VerdictStatus.partially_supported
        elif comparison_estimate.count_b > comparison_estimate.count_a * _COMPARISON_MARGIN:
            status = VerdictStatus.likely_false
        else:
            status = VerdictStatus.mixed

    confidence_label = _confidence_label(score)
    verification_scope = (
        f"독립 지지 근거 {score.independent_support_count}건, 독립 반박 근거 {score.independent_refute_count}건, "
        f"중복·재인용 비율 {score.duplicate_ratio * 100:.0f}%"
    )

    confirmed_points = []
    insufficient_points = []
    if score.independent_support_count:
        confirmed_points.append(f"독립 근거 {score.independent_support_count}건에서 지지하는 내용을 확인했습니다.")
    if score.independent_refute_count:
        confirmed_points.append(f"독립 근거 {score.independent_refute_count}건에서 반박하는 내용을 확인했습니다.")
    if score.evidence_coverage < 0.5:
        insufficient_points.append("검증에 사용된 독립 근거 계통 수가 적어 검증 범위가 제한적입니다.")
    if score.source_conflict >= 0.2:
        insufficient_points.append("자료 간 상충되는 내용이 존재합니다.")

    if comparison_estimate is not None:
        confirmed_points.append(
            f"{comparison_estimate.basis} 비교(근사 지표): '{comparison_estimate.entity_a}' {comparison_estimate.count_a:,}건 vs "
            f"'{comparison_estimate.entity_b}' {comparison_estimate.count_b:,}건. {comparison_estimate.ratio_label}"
        )

    reasoning = _build_reasoning(status, score)
    if comparison_estimate is not None:
        reasoning += (
            f" 참고로 {comparison_estimate.basis}은 '{comparison_estimate.entity_a}' {comparison_estimate.count_a:,}건, "
            f"'{comparison_estimate.entity_b}' {comparison_estimate.count_b:,}건으로 집계되었습니다 (근사 지표)."
        )
    limitations = list(insufficient_points)
    if comparison_estimate is not None:
        limitations.append(f"{comparison_estimate.basis}은 실제 대중 관심도를 완전히 대변하지 않는 근사 지표입니다.")
    if claim.checkability != Checkability.checkable:
        limitations.append(f"이 주장은 checkability={claim.checkability.value}로, 사실 여부보다 해석의 영역일 수 있습니다.")

    return ClaimVerdict(
        claim_id=claim.claim_id,
        claim_text=claim.claim_text,
        claim_type=claim.claim_type,
        status=status,
        confidence_label=confidence_label,
        verification_scope=verification_scope,
        confirmed_points=confirmed_points,
        insufficient_points=insufficient_points,
        reasoning=reasoning,
        limitations=limitations,
        score=score,
    )


def _confidence_label(score: ClaimScore) -> str:
    net = score.support_strength - score.refute_strength
    if score.uncertainty > 0.7:
        return "근거 기반 신뢰도: 낮음 (근거 부족)"
    if abs(net) < 0.2:
        return "근거 기반 신뢰도: 중간 (상충 또는 불확실)"
    if net > 0:
        return "근거 기반 신뢰도: 지지 방향 (절대적 진실 확률 아님)"
    return "근거 기반 신뢰도: 반박 방향 (절대적 진실 확률 아님)"


def _build_reasoning(status: VerdictStatus, score: ClaimScore) -> str:
    return (
        f"독립 지지 {score.independent_support_count}건(강도 {score.support_strength:.2f}), "
        f"독립 반박 {score.independent_refute_count}건(강도 {score.refute_strength:.2f}), "
        f"상충도 {score.source_conflict:.2f}, 불확실성 {score.uncertainty:.2f}를 종합해 "
        f"'{status.value}'로 판정했습니다. 이는 공개된 자료 범위 내의 판단이며 절대적 진실 선언이 아닙니다."
    )
