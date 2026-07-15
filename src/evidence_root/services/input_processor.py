"""세 가지 입력 방식(문장/링크/이미지)을 공통 입력 텍스트로 정규화한다."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..providers.gemini_provider import GeminiProvider
from ..providers.groq_provider import GroqProvider
from . import document_fetcher


@dataclass
class InputBundle:
    input_text: str
    source_kind: str  # "text" | "url" | "image"
    source_url: str = ""
    title: str = ""
    publisher: str = ""
    author: str = ""
    published_at: str | None = None
    canonical_url: str = ""
    body_available: bool = True
    reverse_image_pages: list[dict] = field(default_factory=list)
    used_reverse_image_search: bool = False
    notes: list[str] = field(default_factory=list)


def process_text_input(text: str) -> InputBundle:
    return InputBundle(input_text=text.strip(), source_kind="text")


def process_url_input(url: str) -> InputBundle:
    doc = document_fetcher.fetch_document(url)
    if doc is None or not doc.body_text:
        return InputBundle(
            input_text=f"(본문 미확보) {url}",
            source_kind="url",
            source_url=url,
            body_available=False,
            notes=["본문 미확보: 메타데이터/검색 결과 설명만 사용합니다."],
        )
    combined = f"{doc.title}\n\n{doc.body_text}".strip()
    return InputBundle(
        input_text=combined,
        source_kind="url",
        source_url=url,
        title=doc.title,
        publisher=doc.publisher,
        author=doc.author,
        published_at=doc.published_at,
        canonical_url=doc.canonical_url or url,
        body_available=True,
    )


def process_image_input(
    image_bytes: bytes, corrected_text: str | None, gemini: GeminiProvider, groq: GroqProvider
) -> InputBundle:
    ocr_text = corrected_text
    if not ocr_text:
        if groq.is_configured():
            ocr_text = groq.extract_text_from_image(image_bytes) or ""
        else:
            ocr_text = _gemini_ocr(image_bytes, gemini) or ""

    bundle = InputBundle(input_text=ocr_text.strip(), source_kind="image")
    bundle.notes.append("역이미지 검색 기능은 비활성화되어 있습니다.")
    return bundle


def _gemini_ocr(image_bytes: bytes, gemini: GeminiProvider) -> str | None:
    if not gemini.is_configured():
        return None
    try:
        import base64

        client = gemini._get_client()
        from google.genai import types

        resp = client.models.generate_content(
            model=gemini.model_name,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                "이 이미지에 있는 모든 텍스트를 그대로 추출해줘. 설명 없이 텍스트만 출력해.",
            ],
        )
        return getattr(resp, "text", None)
    except Exception:
        return None
