"""API 설정 화면 (스펙 5장). 관리자 비밀번호로 보호되며, 키를 화면에서 입력/테스트/저장/삭제한다."""
from __future__ import annotations

import streamlit as st

from .. import config
from ..provider_registry import get_registry
from ..security.secret_store import mask_key

_PROVIDER_KEY_MAP = {
    "NAVER_CLIENT_ID": "naver_news",
    "NAVER_CLIENT_SECRET": "naver_news",
    "GROQ_API_KEY": "groq",
    "GOOGLE_FACTCHECK_API_KEY": "google_factcheck",
}

_PURPOSE = {
    "GROQ_API_KEY": "주장 분해, 관련성 평가, 지지/반박 분석, 요약·후속질문 생성까지 전 구간에 사용",
    "GROQ_MODEL": "사용할 Groq 모델명 (예: llama-3.1-8b-instant, 비워두면 자동 선택)",
    "NAVER_CLIENT_ID": "네이버 뉴스/웹/블로그 검색에 사용",
    "NAVER_CLIENT_SECRET": "네이버 뉴스/웹/블로그 검색에 사용",
    "GOOGLE_FACTCHECK_API_KEY": "기존 팩트체크 자료 검색(선택)",
}


def _is_admin_unlocked() -> bool:
    admin_password = config.get_admin_password()
    if not admin_password:
        return not config.is_cloud_env()  # 로컬 개발환경은 비밀번호 없이 허용
    return st.session_state.get("_admin_unlocked", False)


def _render_admin_gate() -> bool:
    admin_password = config.get_admin_password()
    if not admin_password:
        if config.is_cloud_env():
            st.warning("공개 배포 환경이며 관리자 비밀번호(APP_ADMIN_PASSWORD)가 설정되지 않아 API 저장·삭제가 비활성화됩니다.")
            return False
        return True

    if st.session_state.get("_admin_unlocked"):
        return True

    st.info("API 설정 화면은 관리자 비밀번호로 보호되어 있습니다.")
    pw = st.text_input("관리자 비밀번호", type="password", key="_admin_pw_input")
    if st.button("잠금 해제"):
        if pw == admin_password:
            st.session_state["_admin_unlocked"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False


def _render_key_card(name: str, required: bool, allow_write: bool) -> None:
    current = config.resolve_secret(name)
    label = config.KEY_LABELS.get(name, name)
    purpose = _PURPOSE.get(name, "")

    with st.container(border=True):
        st.markdown(f"**{label}** {'(필수)' if required else '(선택)'}")
        st.caption(purpose)

        status = "🟢 연결됨" if current else "⚪ 미설정"
        st.write(f"상태: {status}")
        st.write(f"저장된 키: `{mask_key(current)}`")

        if not allow_write:
            st.caption("현재 환경에서는 저장/삭제가 비활성화되어 있습니다.")
            return

        input_key = f"_input_{name}"
        cols = st.columns([3, 1, 1])
        new_value = cols[0].text_input(
            "새 값 입력", type="password", key=input_key, label_visibility="collapsed",
            placeholder=f"{label} 입력",
        )

        if cols[1].button("연결 테스트", key=f"_test_{name}"):
            _run_connection_test(name, new_value or current)

        if cols[2].button("삭제", key=f"_del_{name}"):
            config.delete_secret(name)
            get_registry()  # 인스턴스는 다음 호출 시 fingerprint 변화로 자동 재생성
            st.success(f"{label} 삭제 완료")
            st.rerun()

        if st.button("저장하고 적용", key=f"_save_{name}"):
            if not new_value:
                st.warning("저장할 값을 입력하세요.")
            else:
                config.save_secret(name, new_value)
                st.success(f"{label} 저장 및 적용 완료")
                if config.is_cloud_env():
                    st.info("현재 세션에는 적용되었지만 서버 재시작 후에는 유지되지 않을 수 있습니다. Streamlit Cloud Secrets에 등록하면 계속 사용할 수 있습니다.")
                st.rerun()

        if name == "GROQ_MODEL":
            st.caption(f"현재 값: {current or '(미설정, 기본값 llama-3.1-8b-instant 사용)'}")


def _run_connection_test(name: str, value: str | None) -> None:
    if not value:
        st.warning("테스트할 값이 없습니다. 먼저 값을 입력하세요.")
        return

    provider_key = _PROVIDER_KEY_MAP.get(name)
    if provider_key is None:
        st.info("이 항목은 별도 연결 테스트가 없습니다 (모델명 등).")
        return

    # 저장하지 않고 임시로 세션에 반영해 테스트
    config.set_secret_session_only(name, value)
    registry = get_registry()
    provider = registry.get(provider_key)
    result = provider.test_connection()
    if result.ok:
        st.success(result.message)
    else:
        st.error(f"[{result.kind.value}] {result.message}")


def render_api_settings_page() -> None:
    st.title("API 설정")
    st.caption("API 키는 이 화면에서만 관리하며, 저장된 값은 마스킹되어 표시됩니다. 전체 키 값은 다시 노출되지 않습니다.")

    if not _render_admin_gate():
        return

    allow_write = _is_admin_unlocked()

    st.subheader("필수 API")
    for name in config.REQUIRED_KEYS:
        _render_key_card(name, required=True, allow_write=allow_write)

    st.subheader("선택 API")
    for name in config.OPTIONAL_KEYS:
        _render_key_card(name, required=False, allow_write=allow_write)
