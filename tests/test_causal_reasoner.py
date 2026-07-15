from evidence_root.schemas import Claim, ClaimScore, ClaimVerdict
from evidence_root.services.causal_reasoner import evaluate_causal_claim


class FakeLLM:
    def __init__(self, response=None):
        self._response = response

    def is_configured(self):
        return True

    def generate_json(self, prompt, system=None):
        return self._response


def _verdict(claim_id, status):
    return ClaimVerdict(
        claim_id=claim_id, claim_text="t", claim_type="event", status=status,
        confidence_label="", verification_scope="", score=ClaimScore(claim_id=claim_id),
    )


def _causal_claim():
    return Claim(
        claim_id="C3", claim_text="A가 B에 영향을 줬다", claim_type="causal",
        checkability="partially_checkable", entities=["A", "B"],
    )


def _premises():
    a = Claim(claim_id="C1", claim_text="A 사건이 있었다", claim_type="event", checkability="checkable")
    b = Claim(claim_id="C2", claim_text="B 사건이 있었다", claim_type="event", checkability="checkable")
    return a, b


def test_returns_none_for_non_causal_claim():
    claim = Claim(claim_id="C1", claim_text="사건", claim_type="event", checkability="checkable", entities=["A", "B"])
    assert evaluate_causal_claim(claim, [claim], {}, FakeLLM()) is None


def test_unconfirmed_premise_blocks_causal_judgment():
    claim = _causal_claim()
    a, b = _premises()
    claims = [claim, a, b]
    verdicts = {"C1": _verdict("C1", "insufficient_evidence"), "C2": _verdict("C2", "likely_true")}

    result = evaluate_causal_claim(claim, claims, verdicts, FakeLLM())

    assert result.premises_confirmed is False
    assert result.plausible is None
    assert "A 사건이 있었다" in result.reasoning


def test_confirmed_premises_use_llm_interpretation():
    claim = _causal_claim()
    a, b = _premises()
    claims = [claim, a, b]
    verdicts = {"C1": _verdict("C1", "confirmed"), "C2": _verdict("C2", "confirmed")}
    llm = FakeLLM({"plausible": True, "reason": "두 사건의 시점상 연결이 합리적입니다."})

    result = evaluate_causal_claim(claim, claims, verdicts, llm)

    assert result.premises_confirmed is True
    assert result.plausible is True


def test_missing_sibling_claims_returns_none():
    claim = _causal_claim()
    assert evaluate_causal_claim(claim, [claim], {}, FakeLLM()) is None
