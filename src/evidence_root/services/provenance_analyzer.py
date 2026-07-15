"""동일 군집 내 자료들 사이의 원출처 관계를 추정한다 (스펙 15장). 확실하지 않으면 '추정'으로 표시."""
from __future__ import annotations

from ..schemas import Evidence, ProvenanceEdge, RelationType


def analyze_provenance(evidences: list[Evidence]) -> list[ProvenanceEdge]:
    edges: list[ProvenanceEdge] = []
    clusters: dict[str, list[Evidence]] = {}
    for e in evidences:
        if not e.duplicate_cluster_id:
            continue
        clusters.setdefault(e.duplicate_cluster_id, []).append(e)

    for cluster_id, members in clusters.items():
        if len(members) < 2:
            continue

        def sort_key(e: Evidence):
            return (e.published_at or "9999", e.evidence_id)

        ordered = sorted(members, key=sort_key)
        origin = ordered[0]
        for follower in ordered[1:]:
            relation = _guess_relation(origin, follower)
            edges.append(
                ProvenanceEdge(
                    source_evidence_id=follower.evidence_id,
                    target_evidence_id=origin.evidence_id,
                    relation=relation,
                    is_estimated=True,
                    reason=f"같은 근거 계통(cluster={cluster_id}) 내 발행시각/출처표현 기반 추정",
                )
            )
    return edges


def _guess_relation(origin: Evidence, follower: Evidence) -> RelationType:
    origin_type = origin.source_type
    follower_body = (follower.body_text or follower.snippet or "").lower()
    if origin.publisher and origin.publisher.lower() in follower_body:
        return RelationType.cites
    if origin_type.value in ("official_statement", "official_statistics", "corporate_disclosure"):
        return RelationType.derived_from
    if follower.source_type.value == "news_republication":
        return RelationType.republishes
    return RelationType.unknown
