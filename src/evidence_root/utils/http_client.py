"""공용 HTTP 클라이언트. timeout/retry/동시성 제한/응답 크기 제한을 적용한다.

Streamlit 스크립트 실행 모델과 맞추기 위해 동기 httpx.Client + ThreadPoolExecutor 조합을 사용한다.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Callable, TypeVar

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .. import config

logger = logging.getLogger("evidence_root.http")

USER_AGENT = "EvidenceRootBot/1.0 (+fact-checking research tool)"
MAX_RESPONSE_BYTES = 3_000_000

T = TypeVar("T")


def new_client(timeout: float | None = None) -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(timeout or config.HTTP_TIMEOUT_SECONDS), follow_redirects=True)


# 기사 본문 스크래핑 전용 짧은 타임아웃. 크롤링을 막는 사이트는 재시도해도 대부분 다시 실패하므로
# 오래 기다리기보다 빨리 포기하고 다음 자료로 넘어가는 쪽이 전체 분석 속도에 유리하다.
DOCUMENT_FETCH_TIMEOUT_SECONDS = 6.0


def new_document_fetch_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(DOCUMENT_FETCH_TIMEOUT_SECONDS), follow_redirects=True)


@retry(
    reraise=True,
    stop=stop_after_attempt(1),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
)
def fetch_url(client: httpx.Client, url: str) -> tuple[int, str, str]:
    """(status_code, content_type, text) 반환. 응답 크기를 제한한다."""
    with client.stream("GET", url, headers={"User-Agent": USER_AGENT}) as resp:
        content_type = resp.headers.get("content-type", "")
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_bytes():
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                break
            chunks.append(chunk)
        body = b"".join(chunks)
        try:
            text = body.decode(resp.encoding or "utf-8", errors="replace")
        except (LookupError, TypeError):
            text = body.decode("utf-8", errors="replace")
        return resp.status_code, content_type, text


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
)
def request_json(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    kwargs.setdefault("timeout", config.HTTP_TIMEOUT_SECONDS)
    return client.request(method, url, **kwargs)


def run_concurrently(
    func: Callable[..., T], items: list, max_workers: int | None = None, timeout: float = 60.0
) -> list[T]:
    """items 각각에 func를 병렬 적용하고, 개별 예외/시간초과는 로그 후 None으로 대체한다.

    느리게 응답하는 서버 하나 때문에 전체 배치가 무한정 멈추지 않도록 작업별 timeout을 둔다.
    시간 초과된 스레드는 백그라운드에서 계속 실행되다 종료되지만 결과는 버려진다(shutdown(wait=False)).
    """
    workers = max_workers or config.MAX_CONCURRENT_REQUESTS
    results: list[T] = [None] * len(items)  # type: ignore[list-item]
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = {pool.submit(func, item): idx for idx, item in enumerate(items)}
        for future in futures:
            idx = futures[future]
            try:
                results[idx] = future.result(timeout=timeout)
            except FutureTimeoutError:
                logger.warning("동시 작업 시간 초과 idx=%s", idx)
                results[idx] = None  # type: ignore[assignment]
            except Exception as exc:
                logger.warning("동시 작업 실패 idx=%s err=%s", idx, exc)
                results[idx] = None  # type: ignore[assignment]
    finally:
        pool.shutdown(wait=False)
    return results
