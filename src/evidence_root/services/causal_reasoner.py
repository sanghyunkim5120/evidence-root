"""인과관계 주장(A가 B에 영향을 줬다)은 뉴스 기사에서 그 인과관계 자체를 직접 서술한 문장을
찾기 어려운 경우가 대부분이다. 이미 확인된 전제 사실(개별 사건 주장의 판정)을 바탕으로 LLM이
논리적으로 해석하도록 하고, 이건 새로운 사실 확인이 아니라 '해석'임을 명확히 표시한다."""
from __future__ import annotations

from dataclasses import dataclass

from ..providers.base import TextLLMProvider
from ..schemas import Claim, ClaimVerdict, VerdictStatus

_UNCONFIRMED_STATUSES = {
    VerdictStatus.insufficient_evidence,
    VerdictStatus.false,
    VerdictStatus.unverifiable,
    VerdictStatus.likely_false,
}

PROMPT = """다음 인과관계 주장을 뉴스 기사 근거를 새로 찾지 말고, 이미 확인된 전제 사실을 바탕으로
논리적으로 해석하라. 이것은 새로운 사실 확인이 아니라 '해석'이다. 전제만으로 인과관계까지 단정할 수
없으면 plausible을 null로 두고 그렇게 설명하라. 과장하지 마라.

인과 주장: {claim_text}

전제 사실 1: {premise_a} → 판정: {status_a}
전제 사실 2: {premise_b} → 판정: {status_b}

JSON으로만 응답: {{"plausible": true/false/null, "reason": "전제 기반 추론 근거 (해석임을 명시)"}}
"""


@dataclass
class CausalAssessment:
    reasoning: str
    plausible: bool | None  # None = 판단 보류/불가
    premises_confirmed: bool


def _find_premise_claim(entity: str, claims: list[Claim], exclude_id: str) -> Claim | None:
    for c in claims:
        if c.claim_id == exclude_id or c.claim_type == "causal":
            continue
        haystack = " ".join([c.claim_text, *c.entities, *c.keywords])
        if entity and entity in haystack:
            return c
    return None


def evaluate_causal_claim(
    claim: Claim,
    claims: list[Claim],
    verdicts_by_claim_id: dict[str, ClaimVerdict],
    llm: TextLLMProvider,
) -> CausalAssessment | None:
    if claim.claim_type != "causal" or len(claim.entities) < 2:
        return None

    premise_a = _find_premise_claim(claim.entities[0], claims, claim.claim_id)
    premise_b = _find_premise_claim(claim.entities[1], claims, claim.claim_id)
    if premise_a is None or premise_b is None:
        return None

    verdict_a = verdicts_by_claim_id.get(premise_a.claim_id)
    verdict_b = verdicts_by_claim_id.get(premise_b.claim_id)
    if verdict_a is None or verdict_b is None:
        return None

    unconfirmed = [p.claim_text for p, v in ((premise_a, verdict_a), (premise_b, verdict_b)) if v.status in _UNCONFIRMED_STATUSES]
    if unconfirmed:
        return CausalAssessment(
            reasoning=f"전제가 되는 사건이 확인되지 않았습니다: {', '.join(unconfirmed)}. 전제가 불확실하므로 인과관계를 판단할 수 없습니다.",
            plausible=None,
            premises_confirmed=False,
        )

    if not llm.is_configured():
        return CausalAssessment(
            reasoning="전제 사실은 확인되었으나, 인과관계를 해석할 LLM이 설정되지 않아 판단을 보류합니다.",
            plausible=None,
            premises_confirmed=True,
        )

    raw = llm.generate_json(
        PROMPT.format(
            claim_text=claim.claim_text,
            premise_a=premise_a.claim_text,
            status_a=verdict_a.status.value,
            premise_b=premise_b.claim_text,
            status_b=verdict_b.status.value,
        )
    )
    if not isinstance(raw, dict):
        return CausalAssessment(
            reasoning="전제 사실은 확인되었으나, 인과관계 해석 응답을 받지 못해 판단을 보류합니다.",
            plausible=None,
            premises_confirmed=True,
        )

    return CausalAssessment(
        reasoning=raw.get("reason", ""),
        plausible=raw.get("plausible"),
        premises_confirmed=True,
    )
