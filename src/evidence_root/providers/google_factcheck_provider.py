from __future__ import annotations

import logging

from .. import config
from ..utils.http_client import new_client, request_json
from .base import BaseProvider, ConnectionErrorKind, ConnectionTestResult, RawSearchResult

logger = logging.getLogger("evidence_root.providers.factcheck")

FACTCHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


class GoogleFactCheckProvider(BaseProvider):
    provider_name = "google_factcheck"

    def __init__(self) -> None:
        self.api_key = config.resolve_secret("GOOGLE_FACTCHECK_API_KEY")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def test_connection(self) -> ConnectionTestResult:
        if not self.is_configured():
            return ConnectionTestResult(False, ConnectionErrorKind.not_configured, "Google Fact Check API Key가 설정되지 않았습니다.")
        try:
            with new_client() as client:
                resp = request_json(client, "GET", FACTCHECK_URL, params={"query": "test", "key": self.api_key})
            if resp.status_code == 200:
                return ConnectionTestResult(True, ConnectionErrorKind.ok, "Google Fact Check API 연결 성공")
            if resp.status_code in (401, 403):
                return ConnectionTestResult(False, ConnectionErrorKind.auth_failed, "인증 실패: API Key를 확인하세요.")
            if resp.status_code == 429:
                return ConnectionTestResult(False, ConnectionErrorKind.rate_limited, "사용량 제한에 도달했습니다.")
            return ConnectionTestResult(False, ConnectionErrorKind.unknown_error, f"status={resp.status_code}")
        except Exception as exc:
            return ConnectionTestResult(False, ConnectionErrorKind.network_error, f"네트워크 오류: {exc}")

    def search(self, query: str, page_size: int = 10) -> list[RawSearchResult]:
        if not self.is_configured():
            return []
        try:
            with new_client() as client:
                resp = request_json(
                    client,
                    "GET",
                    FACTCHECK_URL,
                    params={"query": query, "languageCode": "ko", "pageSize": page_size, "key": self.api_key},
                )
            if resp.status_code != 200:
                logger.warning("factcheck 검색 실패 status=%s", resp.status_code)
                return []
            data = resp.json()
            results = []
            for claim in data.get("claims", []):
                for review in claim.get("claimReview", []):
                    results.append(
                        RawSearchResult(
                            url=review.get("url", ""),
                            title=claim.get("text", ""),
                            snippet=f"{review.get('publisher', {}).get('name', '')} 판정: {review.get('textualRating', '')}",
                            publisher=review.get("publisher", {}).get("name", ""),
                            published_at=review.get("reviewDate"),
                            search_provider=self.provider_name,
                            extra={"textual_rating": review.get("textualRating", "")},
                        )
                    )
            return results
        except Exception as exc:
            logger.warning("factcheck 검색 예외: %s", exc)
            return []
