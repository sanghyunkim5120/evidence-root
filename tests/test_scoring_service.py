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
