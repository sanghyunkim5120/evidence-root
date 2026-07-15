"""단일 Gemini 클라이언트. 주장 추출/관련성 평가/stance 분석/요약/후속질문 생성에 재사용된다."""
from __future__ import annotations

import logging
import re
import time

from .. import config
from .base import BaseProvider, ConnectionErrorKind, ConnectionTestResult, TextLLMProvider, parse_json_response

logger = logging.getLogger("evidence_root.providers.gemini")

_RETRY_DELAY_RE = re.compile(r"retry in ([\d.]+)s")
_MAX_RATE_LIMIT_RETRIES = 3
_MAX_WAIT_SECONDS = 35.0


class GeminiProvider(BaseProvider, TextLLMProvider):
    provider_name = "gemini"

    def __init__(self) -> None:
        self.api_key = config.resolve_secret("GEMINI_API_KEY")
        self.model_name = config.resolve_secret("GEMINI_MODEL") or "gemini-2.0-flash"
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is not None:
            return self._client
        from google import genai

        self._client = genai.Client(api_key=self.api_key)
        return self._client

    def test_connection(self) -> ConnectionTestResult:
        if not self.is_configured():
            return ConnectionTestResult(False, ConnectionErrorKind.not_configured, "Gemini API Key가 설정되지 않았습니다.")
        try:
            client = self._get_client()
            resp = client.models.generate_content(model=self.model_name, contents="ping")
            if resp is not None:
                return ConnectionTestResult(True, ConnectionErrorKind.ok, "Gemini 연결 성공")
            return ConnectionTestResult(False, ConnectionErrorKind.unknown_error, "빈 응답")
        except Exception as exc:
            return ConnectionTestResult(*_classify_gemini_error(exc))

    def generate_text(self, prompt: str, system: str | None = None) -> str | None:
        if not self.is_configured():
            return None
        client = self._get_client()
        kwargs = {}
        if system:
            kwargs["config"] = {"system_instruction": system}

        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            try:
                resp = client.models.generate_content(model=self.model_name, contents=prompt, **kwargs)
                return getattr(resp, "text", None)
            except Exception as exc:
                msg = str(exc)
                is_rate_limited = "RESOURCE_EXHAUSTED" in msg or "429" in msg
                if is_rate_limited and attempt < _MAX_RATE_LIMIT_RETRIES:
                    match = _RETRY_DELAY_RE.search(msg)
                    delay = min(float(match.group(1)), _MAX_WAIT_SECONDS) if match else 12.0
                    logger.warning(
                        "Gemini 사용량 제한, %.1f초 대기 후 재시도 (%d/%d)", delay, attempt + 1, _MAX_RATE_LIMIT_RETRIES
                    )
                    time.sleep(delay + 0.5)
                    continue
                logger.warning("Gemini generate_text 실패: %s", exc)
                return None
        return None

    def generate_json(self, prompt: str, system: str | None = None) -> dict | list | None:
        """JSON 응답을 요청하고 파싱한다. 실패 시 None."""
        text = self.generate_text(
            prompt + "\n\n반드시 순수 JSON만 응답하라. 코드블록, 설명, 마크다운을 포함하지 마라.",
            system=system,
        )
        return parse_json_response(text)


def _classify_gemini_error(exc: Exception) -> tuple[bool, ConnectionErrorKind, str]:
    msg = str(exc)
    lower = msg.lower()
    if "api key" in lower or "unauthorized" in lower or "permission" in lower or "401" in lower:
        return False, ConnectionErrorKind.auth_failed, "인증 실패: API Key를 확인하세요."
    if "quota" in lower or "rate" in lower or "429" in lower:
        return False, ConnectionErrorKind.rate_limited, "사용량 제한에 도달했습니다."
    if "model" in lower and ("not found" in lower or "404" in lower):
        return False, ConnectionErrorKind.model_error, "모델명을 확인하세요."
    if "timeout" in lower or "connection" in lower or "network" in lower:
        return False, ConnectionErrorKind.network_error, "네트워크 오류가 발생했습니다."
    return False, ConnectionErrorKind.unknown_error, f"알 수 없는 오류: {msg[:200]}"
