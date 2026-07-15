"""Groq (OpenAI 호환 Chat Completions) 기반 텍스트 LLM Provider. Gemini보다 무료 등급 한도가 넉넉해
주장 추출/관련성 평가/지지반박 분석/요약/후속질문 생성 등 텍스트 분석 전 구간에 우선 사용된다."""
from __future__ import annotations

import logging
import re
import time

from .. import config
from ..utils.http_client import new_client, request_json
from .base import BaseProvider, ConnectionErrorKind, ConnectionTestResult, TextLLMProvider, parse_json_response

logger = logging.getLogger("evidence_root.providers.groq")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# 8b 모델은 하루 토큰 한도가 70b 모델(10만)보다 훨씬 넉넉해(50만) 기본값으로 사용한다.
DEFAULT_MODEL = "llama-3.1-8b-instant"

_RETRY_DELAY_RE = re.compile(r"try again in ([\d.]+)s", re.IGNORECASE)
_MAX_RATE_LIMIT_RETRIES = 2
_MAX_WAIT_SECONDS = 15.0


class GroqProvider(BaseProvider, TextLLMProvider):
    provider_name = "groq"

    def __init__(self) -> None:
        self.api_key = config.resolve_secret("GROQ_API_KEY")
        self.model_name = config.resolve_secret("GROQ_MODEL") or DEFAULT_MODEL

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def test_connection(self) -> ConnectionTestResult:
        if not self.is_configured():
            return ConnectionTestResult(False, ConnectionErrorKind.not_configured, "Groq API Key가 설정되지 않았습니다.")
        try:
            with new_client() as client:
                resp = request_json(
                    client,
                    "POST",
                    GROQ_URL,
                    headers=self._headers(),
                    json={"model": self.model_name, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
                )
            if resp.status_code == 200:
                return ConnectionTestResult(True, ConnectionErrorKind.ok, "Groq 연결 성공")
            return ConnectionTestResult(*_classify_groq_error(resp.status_code, resp.text))
        except Exception as exc:
            return ConnectionTestResult(False, ConnectionErrorKind.network_error, f"네트워크 오류: {exc}")

    def generate_text(self, prompt: str, system: str | None = None) -> str | None:
        if not self.is_configured():
            return None
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        max_tokens = 1400
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            try:
                with new_client() as client:
                    resp = request_json(
                        client, "POST", GROQ_URL, headers=self._headers(),
                        json={"model": self.model_name, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens},
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                if resp.status_code == 429 and attempt < _MAX_RATE_LIMIT_RETRIES:
                    match = _RETRY_DELAY_RE.search(resp.text)
                    delay = min(float(match.group(1)), _MAX_WAIT_SECONDS) if match else 5.0
                    logger.warning("Groq 사용량 제한, %.1f초 대기 후 재시도 (%d/%d)", delay, attempt + 1, _MAX_RATE_LIMIT_RETRIES)
                    time.sleep(delay + 0.5)
                    continue
                if resp.status_code == 413 and max_tokens > 400 and attempt < _MAX_RATE_LIMIT_RETRIES:
                    max_tokens = max_tokens // 2
                    logger.warning("Groq 요청 크기 초과, max_tokens=%d로 줄여서 재시도", max_tokens)
                    continue
                logger.warning("Groq generate_text 실패: status=%s body=%s", resp.status_code, resp.text[:300])
                return None
            except Exception as exc:
                logger.warning("Groq generate_text 예외: %s", exc)
                return None
        return None

    def generate_json(self, prompt: str, system: str | None = None) -> dict | list | None:
        text = self.generate_text(
            prompt + "\n\n반드시 순수 JSON만 응답하라. 코드블록, 설명, 마크다운을 포함하지 마라.",
            system=system,
        )
        return parse_json_response(text)


def _classify_groq_error(status_code: int, body: str) -> tuple[bool, ConnectionErrorKind, str]:
    if status_code in (401, 403):
        return False, ConnectionErrorKind.auth_failed, "인증 실패: API Key를 확인하세요."
    if status_code == 429:
        return False, ConnectionErrorKind.rate_limited, "사용량 제한에 도달했습니다."
    if status_code == 404:
        return False, ConnectionErrorKind.model_error, "모델명을 확인하세요."
    return False, ConnectionErrorKind.unknown_error, f"알 수 없는 오류(status={status_code}): {body[:200]}"
