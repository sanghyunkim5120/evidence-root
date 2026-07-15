"""네이버 검색 API 공용 베이스 + 뉴스/웹/블로그 3종 Provider."""
from __future__ import annotations

import logging
import re

from .. import config
from ..utils.http_client import new_client, request_json
from .base import BaseProvider, ConnectionErrorKind, ConnectionTestResult, RawSearchResult

logger = logging.getLogger("evidence_root.providers.naver")

NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search/{endpoint}.json"


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").replace("&quot;", '"').replace("&amp;", "&")


class _NaverBaseProvider(BaseProvider):
    endpoint = "news"

    def __init__(self) -> None:
        self.client_id = config.resolve_secret("NAVER_CLIENT_ID")
        self.client_secret = config.resolve_secret("NAVER_CLIENT_SECRET")

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _headers(self) -> dict:
        return {
            "X-Naver-Client-Id": self.client_id or "",
            "X-Naver-Client-Secret": self.client_secret or "",
        }

    def test_connection(self) -> ConnectionTestResult:
        if not self.is_configured():
            return ConnectionTestResult(
                False, ConnectionErrorKind.not_configured, "Naver Client ID/Secret이 설정되지 않았습니다."
            )
        try:
            with new_client() as client:
                resp = request_json(
                    client,
                    "GET",
                    NAVER_SEARCH_URL.format(endpoint=self.endpoint),
                    params={"query": "테스트", "display": 1},
                    headers=self._headers(),
                )
            return self._classify_response(resp)
        except Exception as exc:
            return ConnectionTestResult(False, ConnectionErrorKind.network_error, f"네트워크 오류: {exc}")

    def _classify_response(self, resp) -> ConnectionTestResult:
        if resp.status_code == 200:
            return ConnectionTestResult(True, ConnectionErrorKind.ok, "네이버 검색 API 연결 성공")
        if resp.status_code == 401 or resp.status_code == 403:
            return ConnectionTestResult(False, ConnectionErrorKind.auth_failed, "인증 실패: Client ID/Secret을 확인하세요.")
        if resp.status_code == 429:
            return ConnectionTestResult(False, ConnectionErrorKind.rate_limited, "사용량 제한에 도달했습니다.")
        return ConnectionTestResult(
            False, ConnectionErrorKind.unknown_error, f"알 수 없는 오류(status={resp.status_code})"
        )

    def search(self, query: str, display: int = 10) -> list[RawSearchResult]:
        if not self.is_configured():
            return []
        try:
            with new_client() as client:
                resp = request_json(
                    client,
                    "GET",
                    NAVER_SEARCH_URL.format(endpoint=self.endpoint),
                    params={"query": query, "display": min(display, 100), "sort": "date"},
                    headers=self._headers(),
                )
            if resp.status_code != 200:
                logger.warning("naver %s 검색 실패 status=%s", self.endpoint, resp.status_code)
                return []
            data = resp.json()
            results = []
            for item in data.get("items", []):
                results.append(
                    RawSearchResult(
                        url=item.get("originallink") or item.get("link", ""),
                        title=_strip_html(item.get("title", "")),
                        snippet=_strip_html(item.get("description", "")),
                        publisher=item.get("bloggername") or item.get("cafename") or "",
                        published_at=item.get("pubDate") or item.get("postdate"),
                        search_provider=self.provider_name,
                        extra={"link": item.get("link", "")},
                    )
                )
            return results
        except Exception as exc:
            logger.warning("naver %s 검색 예외: %s", self.endpoint, exc)
            return []

    def get_total_count(self, query: str) -> int | None:
        """검색어 전체 매칭 건수(total). 언급량 비교 등 근사 지표로 사용한다."""
        if not self.is_configured():
            return None
        try:
            with new_client() as client:
                resp = request_json(
                    client,
                    "GET",
                    NAVER_SEARCH_URL.format(endpoint=self.endpoint),
                    params={"query": query, "display": 1},
                    headers=self._headers(),
                )
            if resp.status_code != 200:
                return None
            return resp.json().get("total")
        except Exception as exc:
            logger.warning("naver %s total 조회 예외: %s", self.endpoint, exc)
            return None


class NaverNewsSearchProvider(_NaverBaseProvider):
    provider_name = "naver_news"
    endpoint = "news"


class NaverWebSearchProvider(_NaverBaseProvider):
    provider_name = "naver_web"
    endpoint = "webkr"


class NaverBlogSearchProvider(_NaverBaseProvider):
    provider_name = "naver_blog"
    endpoint = "blog"


class NaverCafeSearchProvider(_NaverBaseProvider):
    """네이버 카페(커뮤니티) 검색. 공식 SNS API가 유료라 접근이 어려운 대신, 실사용자 반응·여론이
    드러나는 커뮤니티 글을 공식 Open API로 가져온다. 낮은 신뢰도 가중치(community)로 취급된다."""

    provider_name = "naver_cafe"
    endpoint = "cafearticle"
