"""Provider 인스턴스 캐시. API 키가 바뀌면 관련 Provider를 재생성해 즉시 적용한다."""
from __future__ import annotations

import hashlib

from . import config
from .providers import (
    GeminiProvider,
    GoogleFactCheckProvider,
    GroqProvider,
    NaverBlogSearchProvider,
    NaverCafeSearchProvider,
    NaverNewsSearchProvider,
    NaverWebSearchProvider,
)


def _keys_fingerprint() -> str:
    values = [config.resolve_secret(k) or "" for k in config.ALL_KEYS]
    return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()


class ProviderRegistry:
    def __init__(self) -> None:
        self._fingerprint: str | None = None
        self._providers: dict = {}

    def _ensure_fresh(self) -> None:
        current = _keys_fingerprint()
        if current != self._fingerprint:
            self._fingerprint = current
            self._providers = {
                "gemini": GeminiProvider(),
                "groq": GroqProvider(),
                "naver_news": NaverNewsSearchProvider(),
                "naver_web": NaverWebSearchProvider(),
                "naver_blog": NaverBlogSearchProvider(),
                "naver_cafe": NaverCafeSearchProvider(),
                "google_factcheck": GoogleFactCheckProvider(),
            }

    def get(self, name: str):
        self._ensure_fresh()
        return self._providers[name]

    def text_llm(self):
        """텍스트 분석(주장 추출/관련성/지지반박/요약/후속질문)에 사용할 LLM. Groq가 설정되어 있으면 우선 사용한다."""
        self._ensure_fresh()
        groq = self._providers["groq"]
        if groq.is_configured():
            return groq
        return self._providers["gemini"]

    def search_providers(self) -> list:
        self._ensure_fresh()
        return [
            self._providers["naver_news"],
            self._providers["naver_web"],
            self._providers["naver_blog"],
            self._providers["naver_cafe"],
            self._providers["google_factcheck"],
        ]


_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    return _registry
