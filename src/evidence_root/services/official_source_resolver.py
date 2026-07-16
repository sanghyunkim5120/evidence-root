"""주장 내용을 분석해 원자료를 보유할 가능성이 높은 공식기관 후보 최대 5개를 추정한다 (스펙 11장)."""
from __future__ import annotations

import logging

from ..providers.base import TextLLMProvider
from ..schemas import Claim

logger = logging.getLogger("evidence_root.services.official_source_resolver")

PROMPT_TEMPLATE = """다음 주장을 검증하려면 어떤 공식 기관/자료가 원자료를 갖고 있을 가능성이 높은지 추정하라.
정부·지자체·공공기관, 경찰·소방·군·법원, 통계·공공데이터, 판결·법령·국회 자료, 기업 공시·공식 발표,
연구기관·대학, 국제기구·외국 정부기관 중에서 실제로 관련 있을 만한 후보를 최대 5개 제시하라.
확실하지 않으면 후보를 줄여도 된다. 근거 없이 지어내지 마라.

JSON 배열로만 출력: [{{"organization": "기관명", "category": "분류", "reason": "왜 관련있는지"}}]

주장: {claim_text}
키워드: {keywords}
"""


def resolve_official_sources(claim: Claim, gemini: TextLLMProvider) -> list[dict]:
    if not gemini.is_configured():
        return []
    raw = gemini.generate_json(
        PROMPT_TEMPLATE.format(claim_text=claim.claim_text, keywords=", ".join(claim.keywords))
    )
    if not isinstance(raw, list):
        return []
    candidates = [item for item in raw if isinstance(item, dict) and item.get("organization")]
    return candidates[:5]
