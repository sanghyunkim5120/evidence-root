"""정보 검증 화면 (스펙 4/18/19장)."""
from __future__ import annotations

import streamlit as st

from .. import config
from ..provider_registry import get_registry
from ..schemas import AnalysisResult
from ..services import input_processor
from ..services.analysis_pipeline import run_pipeline
from . import components


def _render_missing_config_notice() -> None:
    st.warning("API 설정이 필요합니다. 필수 API(Groq, Naver 검색)를 설정해야 근거를 검색·분석할 수 있습니다.")
    if st.button("API 설정으로 이동"):
        st.session_state["_nav"] = "API 설정"
        st.rerun()


def _run_analysis(input_text: str) -> AnalysisResult | None:
    if not input_text.strip():
        st.error("분석할 내용이 없습니다.")
        return None

    registry = get_registry()
    status_box = st.status("근거를 확인하는 중입니다...", expanded=True)

    def on_step(name: str) -> None:
        status_box.write(f"진행 단계: {name}")

    try:
        result = run_pipeline(input_text, registry, on_step=on_step)
        status_box.update(label="분석 완료", state="complete")
        return result
    except Exception as exc:
        status_box.update(label="분석 중 오류가 발생했습니다", state="error")
        st.exception(exc)
        return None


def _render_results(result: AnalysisResult) -> None:
    tabs = st.tabs(["종합 분석", "세부 주장", "근거 자료", "출처 관계"])

    with tabs[0]:
        st.subheader("종합 분석")
        st.write(result.overall_summary)
        st.metric("추출된 주장 수", len(result.claims))
        st.metric("전체 자료 수", len(result.evidences))
        independent_count = len({e.duplicate_cluster_id or e.evidence_id for e in result.evidences})
        st.metric("독립 근거 계통 수", independent_count)

        st.markdown("### 후속 질문")
        for i, q in enumerate(result.followup_questions, 1):
            st.write(f"{i}. {q}")

    with tabs[1]:
        st.subheader("세부 주장")
        for verdict in result.verdicts:
            components.render_claim_card(verdict)

    with tabs[2]:
        st.subheader("근거 자료")
        if not result.evidences:
            st.info("수집된 근거 자료가 없습니다.")
        for evidence in result.evidences:
            components.render_evidence_card(evidence, result.stances)

    with tabs[3]:
        st.subheader("출처 관계")
        components.render_provenance_graph(result)


def render_verification_page() -> None:
    st.title("EvidenceRoot")
    st.caption("반복된 정보가 아닌 실제 독립 근거를 확인하세요.")

    if not config.required_keys_configured():
        _render_missing_config_notice()

    text_value = st.text_area("확인하고 싶은 문장이나 게시물 내용을 입력하세요", height=150, key="_input_text")
    input_text: str | None = None
    if st.button("근거 확인 시작", key="_start_text"):
        bundle = input_processor.process_text_input(text_value)
        input_text = bundle.input_text

    if input_text:
        # 새 분석을 시작하면 이전 질문의 결과를 먼저 지운다. 그렇지 않으면 이번 분석이 실패했을 때
        # 화면에 엉뚱하게 이전 질문의 결과가 남아 마치 그게 새 질문의 답인 것처럼 보이게 된다.
        st.session_state.pop("_last_result", None)
        result = _run_analysis(input_text)
        if result:
            st.session_state["_last_result"] = result
        else:
            st.error("이번 분석은 실패했습니다. 위 오류를 확인하고 다시 시도해주세요.")

    if st.session_state.get("_last_result"):
        st.divider()
        _render_results(st.session_state["_last_result"])
