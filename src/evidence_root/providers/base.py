"""Provider 공통 타입. 모든 Provider는 키 미설정/오류 시 예외 대신 빈 결과+에러 사유를 반환한다."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("evidence_root.providers.base")


class ConnectionErrorKind(str, Enum):
    ok = "ok"
    not_configured = "not_configured"
    auth_failed = "auth_failed"
    model_error = "model_error"
    rate_limited = "rate_limited"
    network_error = "network_error"
    invalid_credential_format = "invalid_credential_format"
    unknown_error = "unknown_error"


@dataclass
class ConnectionTestResult:
    ok: bool
    kind: ConnectionErrorKind
    message: str


@dataclass
class RawSearchResult:
    url: str
    title: str = ""
    snippet: str = ""
    publisher: str = ""
    published_at: str | None = None
    search_provider: str = ""
    extra: dict = field(default_factory=dict)


def parse_json_response(text: str | None) -> dict | list | None:
    """LLM 텍스트 응답에서 JSON을 추출한다. 코드블록/설명이 섞여 있어도 최대한 파싱한다."""
    if not text:
        return None
    cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 배치 응답이 토큰 제한으로 중간에 잘린 경우, 완성된 항목만이라도 건져낸다.
        if cleaned.lstrip().startswith("["):
            salvaged = []
            for obj_match in re.finditer(r"\{[^{}]*\}", cleaned):
                try:
                    salvaged.append(json.loads(obj_match.group(0)))
                except json.JSONDecodeError:
                    continue
            if salvaged:
                logger.warning("LLM JSON 응답이 잘려서 %d개 항목만 복구함", len(salvaged))
                return salvaged

        logger.warning("LLM JSON 파싱 실패: %s", cleaned[:200])
        return None


class TextLLMProvider:
    """claim_extractor 등 서비스가 공통으로 의존하는 텍스트 LLM 인터페이스 (Gemini/Groq 등이 구현)."""

    provider_name = "llm"

    def is_configured(self) -> bool:
        raise NotImplementedError

    def generate_text(self, prompt: str, system: str | None = None) -> str | None:
        raise NotImplementedError

    def generate_json(self, prompt: str, system: str | None = None) -> dict | list | None:
        raise NotImplementedError


class BaseProvider:
    provider_name = "base"

    def is_configured(self) -> bool:
        raise NotImplementedError

    def test_connection(self) -> ConnectionTestResult:
        raise NotImplementedError
