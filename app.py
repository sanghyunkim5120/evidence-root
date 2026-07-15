"""EvidenceRoot 진입점. `streamlit run app.py`로 실행한다."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import streamlit as st

from evidence_root.ui.api_settings import render_api_settings_page
from evidence_root.ui.verification_page import render_verification_page

st.set_page_config(page_title="EvidenceRoot", page_icon="🔎", layout="wide")


def main() -> None:
    if "_nav" not in st.session_state:
        st.session_state["_nav"] = "정보 검증"

    with st.sidebar:
        st.markdown("### EvidenceRoot")
        nav = st.radio("메뉴", ["정보 검증", "API 설정"], index=["정보 검증", "API 설정"].index(st.session_state["_nav"]))
        st.session_state["_nav"] = nav

        st.markdown("---")
        st.markdown("#### 분석 모드")
        mode_label = st.radio(
            "분석 모드", ["정밀 분석", "빠른 분석"],
            index=0 if st.session_state.get("analysis_mode", "thorough") == "thorough" else 1,
            label_visibility="collapsed",
        )
        st.session_state["analysis_mode"] = "thorough" if mode_label == "정밀 분석" else "fast"

    if st.session_state["_nav"] == "정보 검증":
        render_verification_page()
    else:
        render_api_settings_page()


main()
