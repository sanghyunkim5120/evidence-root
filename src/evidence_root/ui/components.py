"""결과 화면에서 재사용되는 카드/그래프 컴포넌트."""
from __future__ import annotations

import streamlit as st

from ..schemas import AnalysisResult, ClaimVerdict, Evidence, StanceResult, VerdictStatus

_STATUS_LABELS = {
    VerdictStatus.confirmed: "✅ 확인됨",
    VerdictStatus.likely_true: "🟢 대체로 사실에 가까움",
    VerdictStatus.partially_supported: "🟡 부분적으로 지지됨",
    VerdictStatus.mixed: "🟠 자료 상충",
    VerdictStatus.insufficient_evidence: "⚪ 근거 부족",
    VerdictStatus.likely_false: "🔴 대체로 사실과 다름",
    VerdictStatus.false: "⛔ 반박됨",
    VerdictStatus.unverifiable: "❔ 판단 불가",
}


def render_claim_card(verdict: ClaimVerdict) -> None:
    with st.container(border=True):
        st.markdown(f"#### {verdict.claim_text}")
        st.caption(f"유형: {verdict.claim_type.value}")
        st.markdown(f"**판정: {_STATUS_LABELS.get(verdict.status, verdict.status.value)}**")
        st.write(verdict.confidence_label)
        st.write(f"검증 범위: {verdict.verification_scope}")

        if verdict.confirmed_points:
            st.markdown("**확인된 내용**")
            for p in verdict.confirmed_points:
                st.markdown(f"- {p}")
        if verdict.insufficient_points:
            st.markdown("**근거 부족 내용**")
            for p in verdict.insufficient_points:
                st.markdown(f"- {p}")

        st.markdown("**판정 이유**")
        st.write(verdict.reasoning)

        if verdict.limitations:
            st.markdown("**분석 한계**")
            for l in verdict.limitations:
                st.markdown(f"- {l}")


def render_evidence_card(evidence: Evidence, stances: list[StanceResult]) -> None:
    stance_map = {"support": "지지", "refute": "반박", "mixed": "일부 해당", "insufficient": "근거 부족", "unrelated": "무관"}
    related_stances = [s for s in stances if s.evidence_id == evidence.evidence_id]

    with st.container(border=True):
        st.markdown(f"**{evidence.title or '(제목 없음)'}**")
        meta = " · ".join(filter(None, [evidence.publisher, evidence.published_at, evidence.source_type.value]))
        st.caption(meta)

        origin_label = "원자료/독립취재" if evidence.source_type.value in (
            "official_statement", "official_statistics", "original_reporting", "legal_document", "corporate_disclosure"
        ) else "재인용 가능성"
        st.write(f"자료 성격: {origin_label}")

        for s in related_stances:
            st.write(f"상태: {stance_map.get(s.stance.value, s.stance.value)} (신뢰도 {s.confidence:.2f})")
            if s.relevant_quote:
                st.markdown(f"> {s.relevant_quote}")
            if s.limitations:
                st.caption("한계: " + ", ".join(s.limitations))

        if evidence.url:
            st.markdown(f"[원문 링크]({evidence.url})")

        if evidence.duplicate_cluster_id:
            st.caption(f"근거 계통: {evidence.duplicate_cluster_id}")


_RELATION_LABELS = {
    "cites": "인용함",
    "republishes": "재게재함",
    "summarizes": "요약함",
    "derived_from": "이 자료를 바탕으로 작성됨",
    "independently_reports": "독립적으로 취재함",
    "unknown": "관계 불명확",
}


def render_provenance_graph(result: AnalysisResult) -> None:
    """근거 계통(중복/재인용 군집)을 카드 목록으로 보여준다. 그래프 대신 읽기 쉬운 목록 형태를 사용한다."""
    evidence_by_id = {e.evidence_id: e for e in result.evidences}

    clusters: dict[str, list] = {}
    for edge in result.provenance_edges:
        origin = evidence_by_id.get(edge.target_evidence_id)
        follower = evidence_by_id.get(edge.source_evidence_id)
        if origin is None or follower is None:
            continue
        cluster_id = origin.duplicate_cluster_id or origin.evidence_id
        clusters.setdefault(cluster_id, {"origin": origin, "followers": []})
        clusters[cluster_id]["followers"].append((follower, edge))

    if not clusters:
        st.info("같은 원출처를 공유하는 자료 묶음이 없습니다 (모든 근거가 서로 독립적으로 수집되었습니다).")
        return

    st.caption("같은 원출처에서 나온 자료들을 하나로 묶어 보여줍니다. 독립 근거 계산 시 이 묶음은 1건으로 처리됩니다.")

    for cluster_id, data in clusters.items():
        origin = data["origin"]
        followers = data["followers"]
        with st.container(border=True):
            st.markdown(f"**근거 계통** · 자료 {len(followers) + 1}건")

            st.markdown(f"🔹 **{origin.title or '(제목 없음)'}** — {origin.publisher or '출처 미상'}")
            if origin.url:
                st.caption(origin.url)

            for follower, edge in followers:
                relation_label = _RELATION_LABELS.get(edge.relation.value, edge.relation.value)
                estimated = " (추정)" if edge.is_estimated else ""
                st.markdown(f"　↳ **{follower.title or '(제목 없음)'}** — {follower.publisher or '출처 미상'}")
                st.caption(f"　　{relation_label}{estimated}" + (f" · {follower.url}" if follower.url else ""))
