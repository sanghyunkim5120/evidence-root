from datetime import datetime, timezone

from evidence_root.schemas import Claim, Evidence, Stance, StanceResult
from evidence_root.services.scoring_service import compute_score


def _claim():
    return Claim(claim_id="C1", claim_text="사건이 있었다", claim_type="event", checkability="checkable")


def test_recent_evidence_contributes_more_than_old_evidence():
    claim = _claim()
    recent = Evidence(
        evidence_id="E1", claim_id="C1", url="https://a.com/1", source_type="news_report",
        duplicate_cluster_id="c1", published_at=datetime.now(timezone.utc).strftime("%Y%m%d"),
    )
    old = Evidence(
        evidence_id="E2", claim_id="C1", url="https://b.com/2", source_type="news_report",
        duplicate_cluster_id="c2", published_at="20200101",
    )
    stances = [
        StanceResult(claim_id="C1", evidence_id="E1", stance=Stance.support, confidence=1.0),
    ]
    score_recent = compute_score(claim, [recent], stances)

    stances_old = [StanceResult(claim_id="C1", evidence_id="E2", stance=Stance.support, confidence=1.0)]
    score_old = compute_score(claim, [old], stances_old)

    assert score_recent.support_strength > score_old.support_strength


def test_evidence_near_claim_event_date_outscores_evidence_near_today():
    """주장에 사건 날짜(2023년 3월)가 있으면, 오늘 기준으로 오래된 자료라도 그 사건 시점에 바로 나온
    보도가, 오늘 기준으로만 최신인(하지만 사건과 무관한 시점의) 자료보다 높은 점수를 받아야 한다."""
    claim = Claim(
        claim_id="C1", claim_text="2023년 3월 사건이 있었다", claim_type="event", checkability="checkable",
        dates=["2023년 3월"],
    )
    contemporaneous = Evidence(
        evidence_id="E1", claim_id="C1", url="https://a.com/1", source_type="news_report",
        duplicate_cluster_id="c1", published_at="20230305",
    )
    stances = [StanceResult(claim_id="C1", evidence_id="E1", stance=Stance.support, confidence=1.0)]
    score = compute_score(claim, [contemporaneous], stances)

    # event_date 보정이 없었다면(오늘 기준 3년 전) 0.4배로 깎였을 것 — 실제로는 사건 시점 기준 1.0배가 되어야 한다
    assert score.support_strength > 0.5
