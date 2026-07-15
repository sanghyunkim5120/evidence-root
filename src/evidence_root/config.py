"""설정/키 조회 로직. 스펙 6장의 우선순위를 구현한다.

로컬 실행: SecretStore(Keyring→Fernet 파일) 1순위, 이후 st.secrets, 환경변수.
Streamlit Cloud: 세션 입력 → Supabase(선택) → st.secrets → 환경변수.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from .security.secret_store import get_secret_store

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", override=False)

REQUIRED_KEYS = ["GROQ_API_KEY", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"]
OPTIONAL_KEYS = [
    "GROQ_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GOOGLE_FACTCHECK_API_KEY",
]
ALL_KEYS = REQUIRED_KEYS + OPTIONAL_KEYS

KEY_LABELS = {
    "GEMINI_API_KEY": "Gemini API Key",
    "GEMINI_MODEL": "Gemini 모델명",
    "NAVER_CLIENT_ID": "Naver Client ID",
    "NAVER_CLIENT_SECRET": "Naver Client Secret",
    "GROQ_API_KEY": "Groq API Key",
    "GROQ_MODEL": "Groq 모델명",
    "GOOGLE_FACTCHECK_API_KEY": "Google Fact Check API Key",
}


def is_cloud_env() -> bool:
    return os.environ.get("APP_ENV", "development").lower() == "production" or bool(
        os.environ.get("STREAMLIT_RUNTIME") or os.environ.get("HOSTNAME", "").startswith("streamlit")
    )


def _session_value(name: str) -> Optional[str]:
    try:
        import streamlit as st

        val = st.session_state.get("_session_secrets", {}).get(name)
        return val or None
    except Exception:
        return None


def _st_secrets_value(name: str) -> Optional[str]:
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name]) or None
    except Exception:
        pass
    return None


def resolve_secret(name: str) -> Optional[str]:
    """우선순위대로 키 값을 조회한다. 어떤 소스도 값을 갖고 있지 않으면 None."""
    session_val = _session_value(name)
    if session_val:
        return session_val

    try:
        store_val = get_secret_store().get(name)
        if store_val:
            return store_val
    except Exception:
        pass

    secrets_val = _st_secrets_value(name)
    if secrets_val:
        return secrets_val

    env_val = os.environ.get(name)
    if env_val:
        return env_val

    return None


def set_secret_session_only(name: str, value: str) -> None:
    """Cloud에서 영구 저장소가 없을 때 현재 세션에만 적용."""
    import streamlit as st

    st.session_state.setdefault("_session_secrets", {})[name] = value


def save_secret(name: str, value: str) -> None:
    get_secret_store().set(name, value)
    set_secret_session_only(name, value)


def delete_secret(name: str) -> None:
    get_secret_store().delete(name)
    try:
        import streamlit as st

        st.session_state.get("_session_secrets", {}).pop(name, None)
    except Exception:
        pass


def is_configured(name: str) -> bool:
    return bool(resolve_secret(name))


def required_keys_configured() -> bool:
    return all(is_configured(k) for k in REQUIRED_KEYS)


def get_analysis_mode() -> str:
    try:
        import streamlit as st

        return st.session_state.get("analysis_mode", os.environ.get("ANALYSIS_MODE", "thorough"))
    except Exception:
        return os.environ.get("ANALYSIS_MODE", "thorough")


def get_admin_password() -> Optional[str]:
    return os.environ.get("APP_ADMIN_PASSWORD") or None


HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "15"))
MAX_CONCURRENT_REQUESTS = int(os.environ.get("MAX_CONCURRENT_REQUESTS", "8"))
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS", "3"))
