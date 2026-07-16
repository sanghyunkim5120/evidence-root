"""자료가 주장을 지지/반박/부족 하는지 분석하고, 인용문이 실제 본문에 있는지 코드로 검증한다 (스펙 16장)."""
from __future__ import annotations

import logging

from ..providers.base import TextLLMProvider
from ..schemas import Claim, Evidence, Stance, StanceResult
from ..utils.quote_verifier import quote_exists_in_text

logger = logging.getLogger("evidence_root.services.stance_analyzer")

_DIRECT_SOURCE_TYPES = {"official_statement", "legal_document", "corporate_disclosure"}

PROMPT_TEMPLATE = """다음 주장에 대해 아래 자료가 지지(support)/반박(refute)/일부만 해당(mixed)/근거 부족(insufficient)/
무관(unrelated) 중 무엇인지 판단하라. 의도(intent) 주장은 직접적인 내부 문서·발언·지시가 없으면 반드시
insufficient로 표시하라. relevant_quote는 아래 자료 본문에 실제로 등장하는 문장만 그대로 옮겨써야 한다.
없으면 빈 문자열로 두어라. 지어내지 마라.

**중요**: 주장이 특정 시점의 구체적 사건·발언("A가 B라고 말했다", "A가 B를 했다")을 말하는 경우, 자료가
그 사건/발언을 구체적으로 확인해줄 때만 support로 판단하라. 같은 인물·주제에 대한 일반적인 배경 설명,
정책/독트린 소개, 과거의 유사 사례, 전문가의 일반론은 이 특정 사건을 확인해주지 않는다 — 그런 자료는
반드시 insufficient로 표시하고, support로 착각하지 마라.

주장: {claim_text}

자료 제목: {title}
자료 본문(발췌): {body}

JSON으로만 응답:
{{"stance": "support|refute|mixed|insufficient|unrelated", "confidence": 0.0~1.0,
 "relevant_quote": "본문에 실제 존재하는 문장 또는 빈 문자열", "reason": "판단 이유",
 "limitations": ["확인하지 못한 부분"]}}
"""

BATCH_PROMPT_TEMPLATE = """다음 주장에 대해 아래 자료 목록 각각이 지지(support)/반박(refute)/일부만 해당(mixed)/
근거 부족(insufficient)/무관(unrelated) 중 무엇인지 판단하라. 의도(intent) 주장은 직접적인 내부 문서·발언·지시가
없으면 반드시 insufficient로 표시하라. relevant_quote는 각 자료 본문에 실제로 등장하는 문장만 그대로 옮겨써야
한다. 없으면 빈 문자열로 두어라. 지어내지 마라. reason은 한 문장으로 짧게, limitations는 최대 1개만 적어라.
응답이 잘리지 않도록 간결하게 작성하라.

**중요**: 주장이 특정 시점의 구체적 사건·발언("A가 B라고 말했다", "A가 B를 했다")을 말하는 경우, 자료가
그 사건/발언을 구체적으로 확인해줄 때만 support로 판단하라. 같은 인물·주제에 대한 일반적인 배경 설명,
정책/독트린 소개, 과거의 유사 사례, 전문가의 일반론은 이 특정 사건을 확인해주지 않는다 — 그런 자료는
반드시 insufficient로 표시하고, support로 착각하지 마라.

주장: {claim_text}

자료 목록:
{items}

각 자료의 id에 대해 JSON 배열로만 응답하라:
[{{"id": "E1", "stance": "support|refute|mixed|insufficient|unrelated", "confidence": 0.0~1.0,
 "relevant_quote": "본문에 실제 존재하는 문장 또는 빈 문자열", "reason": "짧은 이유",
 "limitations": ["확인하지 못한 부분(선택)"]}}, ...]
"""


def _build_result(claim: Claim, evidence: Evidence, raw: dict | None, source_text: str) -> StanceResult:
    if not isinstance(raw, dict):
        return StanceResult(
            claim_id=claim.claim_id,
            evidence_id=evidence.evidence_id,
            stance=Stance.insufficient,
            confidence=0.0,
            reason="stance 분석 응답 파싱 실패",
        )

    stance_value = raw.get("stance", "insufficient")
    if stance_value not in {s.value for s in Stance}:
        stance_value = "insufficient"

    quote = (raw.get("relevant_quote") or "").strip()
    verified = quote_exists_in_text(quote, source_text) if quote else False
    if quote and not verified:
        logger.info("인용문이 원문에 존재하지 않아 폐기: evidence=%s", evidence.evidence_id)
        quote = ""

    if claim.claim_type == "intent" and stance_value == "support":
        if not (verified and evidence.source_type.value in _DIRECT_SOURCE_TYPES):
            stance_value = "insufficient"

    return StanceResult(
        claim_id=claim.claim_id,
        evidence_id=evidence.evidence_id,
        stance=Stance(stance_value),
        confidence=float(raw.get("confidence", 0.0) or 0.0),
        relevant_quote=quote,
        reason=raw.get("reason", ""),
        limitations=list(raw.get("limitations", []) or []),
        quote_verified=verified,
    )


def analyze_stance(claim: Claim, evidence: Evidence, gemini: TextLLMProvider) -> StanceResult:
    """단일 근거에 대한 stance 분석 (테스트/소규모 호출용). 대량 처리에는 analyze_stances를 사용한다."""
    source_text = evidence.body_text or evidence.snippet
    if not gemini.is_configured() or not source_text:
        return StanceResult(
            claim_id=claim.claim_id,
            evidence_id=evidence.evidence_id,
            stance=Stance.insufficient,
            confidence=0.0,
            reason="분석에 필요한 본문 또는 LLM 설정이 부족합니다.",
            limitations=["본문 미확보" if not source_text else "LLM 미설정"],
        )

    raw = gemini.generate_json(
        PROMPT_TEMPLATE.format(claim_text=claim.claim_text, title=evidence.title, body=source_text[:3000])
    )
    return _build_result(claim, evidence, raw, source_text)


def analyze_stances(claim: Claim, evidences: list[Evidence], gemini: TextLLMProvider) -> list[StanceResult]:
    """한 주장에 속한 근거 여러 개를 한 번의 LLM 요청으로 묶어 분석한다 (API 호출 횟수 절감)."""
    if not evidences:
        return []

    source_texts = {e.evidence_id: (e.body_text or e.snippet) for e in evidences}
    usable = [e for e in evidences if source_texts[e.evidence_id]]
    unusable = [e for e in evidences if not source_texts[e.evidence_id]]

    results: list[StanceResult] = [
        StanceResult(
            claim_id=claim.claim_id,
            evidence_id=e.evidence_id,
            stance=Stance.insufficient,
            confidence=0.0,
            reason="본문을 확보하지 못했습니다.",
            limitations=["본문 미확보"],
        )
        for e in unusable
    ]

    if not usable:
        return results
    if not gemini.is_configured():
        results.extend(
            StanceResult(
                claim_id=claim.claim_id,
                evidence_id=e.evidence_id,
                stance=Stance.insufficient,
                confidence=0.0,
                reason="LLM이 설정되지 않았습니다.",
                limitations=["LLM 미설정"],
            )
            for e in usable
        )
        return results

    raw_by_id: dict[str, dict] = {}
    chunk_size = 3  # 분당 토큰 한도(TPM)를 넘기지 않도록 작은 묶음으로 나눠 보낸다
    for i in range(0, len(usable), chunk_size):
        chunk = usable[i : i + chunk_size]
        items = "\n\n".join(
            f"id: {e.evidence_id}\n제목: {e.title}\n본문(발췌): {source_texts[e.evidence_id][:600]}" for e in chunk
        )
        raw = gemini.generate_json(BATCH_PROMPT_TEMPLATE.format(claim_text=claim.claim_text, items=items))
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("id"):
                    raw_by_id[item["id"]] = item

    for e in usable:
        results.append(_build_result(claim, e, raw_by_id.get(e.evidence_id), source_texts[e.evidence_id]))

    return results
