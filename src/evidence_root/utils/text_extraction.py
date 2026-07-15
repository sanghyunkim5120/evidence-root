"""본문 수집: trafilatura → BeautifulSoup → JSON-LD → Open Graph → snippet 순 폴백."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("evidence_root.extraction")


@dataclass
class ExtractedDocument:
    title: str = ""
    body_text: str = ""
    publisher: str = ""
    author: str = ""
    published_at: Optional[str] = None
    canonical_url: str = ""
    outbound_links: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    full_text_available: bool = False


def extract_document(html: str, url: str) -> ExtractedDocument:
    doc = ExtractedDocument()

    # 1) trafilatura
    try:
        import trafilatura

        extracted = trafilatura.extract(
            html, url=url, output_format="json", with_metadata=True, favor_precision=True
        )
        if extracted:
            data = json.loads(extracted)
            doc.title = data.get("title") or doc.title
            doc.body_text = data.get("text") or ""
            doc.author = data.get("author") or ""
            doc.published_at = data.get("date")
            doc.publisher = data.get("sitename") or ""
            if data.get("text"):
                doc.full_text_available = True
    except Exception as exc:  # trafilatura가 실패해도 계속 진행
        logger.info("trafilatura 실패 url=%s err=%s", url, exc)

    # 2) BeautifulSoup 보강 (og/json-ld/링크/이미지)
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        if not doc.title:
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                doc.title = og_title["content"]
            elif soup.title:
                doc.title = soup.title.get_text(strip=True)

        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            doc.canonical_url = canonical["href"]

        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content") and not doc.publisher:
            doc.publisher = og_site["content"]

        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            doc.image_urls.append(og_image["content"])

        # JSON-LD 구조화 데이터
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                ld = json.loads(script.string or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            items = ld if isinstance(ld, list) else [ld]
            for item in items:
                if not isinstance(item, dict):
                    continue
                if not doc.author:
                    author = item.get("author")
                    if isinstance(author, dict):
                        doc.author = author.get("name", "")
                    elif isinstance(author, str):
                        doc.author = author
                if not doc.published_at:
                    doc.published_at = item.get("datePublished") or item.get("dateCreated")
                if not doc.publisher:
                    pub = item.get("publisher")
                    if isinstance(pub, dict):
                        doc.publisher = pub.get("name", "")

        if not doc.body_text:
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                doc.body_text = og_desc["content"]

        for a in soup.find_all("a", href=True)[:100]:
            href = a["href"]
            if href.startswith("http"):
                doc.outbound_links.append(href)
    except Exception as exc:
        logger.info("BeautifulSoup 보강 실패 url=%s err=%s", url, exc)

    if not doc.canonical_url:
        doc.canonical_url = url

    return doc
