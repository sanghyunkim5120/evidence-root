"""근거 품질/독립성을 반영해 주장별 점수를 계산한다 (스펙 17장). 가중치는 config/scoring.yaml에서 읽는다."""
from __future__ import annotations

from pathlib import Path

import yaml

from ..schemas import Claim, ClaimScore, Evidence, Stance, StanceResult
from ..utils.date_parsing import recency_weight

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "scoring.yaml"
_config_cache: dict | None = None


def _load_config() -> dict:
    global _config_cache
    if _config_cache is None:
        _config_cache = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    return _config_cache


def compute_score(claim: Claim, evidences: list[Evidence], stances: list[StanceResult]) -> ClaimScore:
    cfg = _load_config()
    weights = cfg.get("evidence_weights", {})
    decay = cfg.get("independence_decay", 0.6)

    evidence_by_id = {e.evidence_id: e for e in evidences}
    claim_stances = [s for s in stances if s.claim_id == claim.claim_id]

    cluster_seen: dict[str, int] = {}
    support_strength = 0.0
    refute_strength = 0.0
    independent_support = 0
    independent_refute = 0

    for s in claim_stances:
        evidence = evidence_by_id.get(s.evidence_id)
        if evidence is None or s.stance == Stance.unrelated:
            continue
        base_weight = weights.get(evidence.source_type.value, 0.2)
        cluster_id = evidence.duplicate_cluster_id or evidence.evidence_id
        occurrence = cluster_seen.get(cluster_id, 0)
        cluster_seen[cluster_id] = occurrence + 1
        independence_factor = decay**occurrence
        recency_factor = recency_weight(evidence.published_at)
        contribution = base_weight * s.confidence * independence_factor * recency_factor

        if s.stance == Stance.support:
            support_strength += contribution
            if occurrence == 0:
                independent_support += 1
        elif s.stance == Stance.refute:
            refute_strength += contribution
            if occurrence == 0:
                independent_refute += 1
        elif s.stance == Stance.mixed:
            support_strength += contribution * 0.5
            refute_strength += contribution * 0.5

    total_evidence = len({s.evidence_id for s in claim_stances})
    total_clusters = len(cluster_seen) or 1
    duplicate_ratio = 1 - (total_clusters / total_evidence) if total_evidence else 0.0

    denom = support_strength + refute_strength
    source_conflict = (
        min(support_strength, refute_strength) / denom if denom > 0 else 0.0
    )
    evidence_coverage = min(1.0, total_clusters / 3) if total_clusters else 0.0
    uncertainty = max(0.0, 1.0 - (support_strength + refute_strength) / 3)

    return ClaimScore(
        claim_id=claim.claim_id,
        support_strength=round(support_strength, 4),
        refute_strength=round(refute_strength, 4),
        evidence_coverage=round(evidence_coverage, 4),
        independent_support_count=independent_support,
        independent_refute_count=independent_refute,
        source_conflict=round(source_conflict, 4),
        uncertainty=round(uncertainty, 4),
        duplicate_ratio=round(max(0.0, duplicate_ratio), 4),
    )
