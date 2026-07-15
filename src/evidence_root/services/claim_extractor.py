"""입력 내용을 세부 주장 최대 3개로 분해한다 (스펙 9장)."""
from __future__ import annotations

import logging

from pydantic import ValidationError

from ..providers.gemini_provider import GeminiProvider
from ..schemas import Checkability, Claim, ClaimType

logger = logging.getLogger("evidence_root.services.claim_extractor")

PROMPT_TEMPLATE = """다음은 사용자가 온라인에서 접한 문장/게시물/기사 내용이다. 이 내용을 서로 다른 검증 방법이 필요한
세부 주장으로 분해하라. 최대 3개까지만 생성한다. 의견/가치판단은 억지로 사실 판정 대상으로 만들지 말고
checkability를 opinion 또는 unverifiable로 표시하라.

**입력에 실제로 쓰여 있지 않은 내용을 지어내서 주장으로 만들지 마라.** "장소/기관이 존재한다" 같은 자명하고
입력에 없는 사실, 입력에 없는 비교("가장 관심받았다" 등)를 새로 만들어내면 안 된다. 입력이 단순한 사실 하나만
담고 있다면 주장을 1개만 만들어라. 억지로 개수를 채우지 마라.

**claim_type을 comparison으로 정하려면 입력 문장 안에 실제로 서로 다른 두 개의 비교 대상(사건/인물/사물)이
명시되어 있어야 한다** (예: "A가 B보다", "A와 B 중", "A 대 B"). 입력에 비교하는 말투("더 관심받았다", "가장
주목받았다" 등)만 있고 무엇과 비교하는지 대상이 안 적혀 있으면, 그건 비교 대상이 없는 것이다 — 이때 같은
사건을 억지로 둘로 쪼개서 가짜 비교 대상(예: "늑대" vs "동물원"처럼 한 사건의 부분들)을 만들어내면 절대
안 된다. 그럴 땐 comparison으로 만들지 말고 event로 취급하되, checkability를 unverifiable로 표시하고
required_evidence에 "비교 대상이 명시되지 않아 검증 불가"라고 적어라.

입력에 실제로 두 개의 서로 다른 비교 대상이 명시되어 있을 때만(예: "A가 B보다 더 관심을 받았다"), 같은
비교 주장을 표현만 바꿔 여러 개 만들지 말고 다음처럼 쪼개라:
1) 비교 대상이 되는 사건 A가 실제로 있었는지 (event, 보통 checkable — 개별 사실 확인)
2) 비교 대상이 되는 사건 B가 실제로 있었는지 (event, 보통 checkable — 개별 사실 확인)
3) A가 B보다 더 (관심/주목 등을) 받았다는 비교 자체 (claim_type=comparison, checkability=partially_checkable —
   이건 보도량·언급량 등 간접 지표로만 근사 검증 가능하다는 점을 keywords와 required_evidence에 명시)

각 주장에 대해 다음 JSON 스키마를 따르는 객체를 만들어라:
{{
  "claim_id": "C1",
  "claim_text": "주장 내용 (원문 표현을 최대한 보존)",
  "claim_type": "event|numerical|comparison|causal|intent|quote|image_context|generalization|other",
  "checkability": "checkable|partially_checkable|opinion|unverifiable",
  "entities": ["관련 인물/사물 (comparison 유형이면 비교 대상 두 개를 넣되, 첫 번째가 주장에서 더 많다/크다고 언급된 대상이 되도록 순서를 맞춰라)"],
  "organizations": ["관련 기관"],
  "locations": ["관련 장소"],
  "dates": ["관련 날짜/기간 표현"],
  "quantities": ["관련 수치"],
  "keywords": ["검색에 사용할 핵심 키워드"],
  "required_evidence": ["이 주장을 검증하려면 필요한 자료 종류"]
}}

claim_id는 C1, C2, C3 순서로 부여하라. 반드시 JSON 배열만 출력하라.

--- 입력 내용 ---
{input_text}
"""


def extract_claims(input_text: str, gemini: GeminiProvider, max_claims: int = 3) -> list[Claim]:
    if not input_text.strip():
        return []
    if not gemini.is_configured():
        logger.warning("Gemini 미설정 - 주장 추출 불가")
        return []

    raw = gemini.generate_json(PROMPT_TEMPLATE.format(input_text=input_text[:6000]))
    claims = _parse_claims(raw)

    if not claims:
        logger.warning("주장 추출 1차 실패, 1회 재시도")
        raw = gemini.generate_json(PROMPT_TEMPLATE.format(input_text=input_text[:6000]))
        claims = _parse_claims(raw)

    if not claims:
        return [
            Claim(
                claim_id="C1",
                claim_text=input_text[:300],
                claim_type="other",
                checkability="unverifiable",
                keywords=[],
            )
        ]

    return claims[:max_claims]


def _parse_claims(raw) -> list[Claim]:
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else raw.get("claims", []) if isinstance(raw, dict) else []
    claims: list[Claim] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item.setdefault("claim_id", f"C{idx + 1}")
        # Gemini가 claim_type/checkability 값을 서로 뒤바꿔 넣는 경우가 있어 방어적으로 보정한다.
        if item.get("claim_type") not in {t.value for t in ClaimType}:
            item["claim_type"] = "other"
        if item.get("checkability") not in {c.value for c in Checkability}:
            item["checkability"] = "unverifiable"
        try:
            claims.append(Claim(**item))
        except ValidationError as exc:
            logger.warning("주장 검증 실패: %s", exc)
    return claims
