"""URL 본문 수집. 실패 시 None을 반환하며 파이프라인 전체를 막지 않는다."""
from __future__ import annotations

import logging

from ..utils.http_client import fetch_url, new_document_fetch_client, run_concurrently
from ..utils.text_extraction import ExtractedDocument, extract_document

logger = logging.getLogger("evidence_root.services.document_fetcher")


def fetch_document(url: str) -> ExtractedDocument | None:
    if not url or not url.startswith("http"):
        return None
    try:
        with new_document_fetch_client() as client:
            status, content_type, text = fetch_url(client, url)
        if status != 200 or "text/html" not in content_type and "text/plain" not in content_type:
            if status != 200:
                logger.info("본문 수집 실패(status=%s) url=%s", status, url)
                return None
        return extract_document(text, url)
    except Exception as exc:
        logger.info("본문 수집 예외 url=%s err=%s", url, exc)
        return None


def fetch_documents(urls: list[str], max_workers: int = 16) -> dict[str, ExtractedDocument | None]:
    docs = run_concurrently(fetch_document, urls, max_workers=max_workers, timeout=15.0)
    return dict(zip(urls, docs))
