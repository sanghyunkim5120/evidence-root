from evidence_root.schemas import Claim, Evidence
from evidence_root.services.stance_analyzer import analyze_stance, analyze_stances


class FakeGemini:
    def __init__(self, response):
        self._response = response
        self.calls = 0

    def is_configured(self):
        return True

    def generate_json(self, prompt, system=None):
        self.calls += 1
        return self._response


def _claim(claim_type="event"):
    return Claim(claim_id="C1", claim_text="회사 임원이 내부적으로 은폐를 지시했다", claim_type=claim_type, checkability="checkable")


def _evidence(body):
    return Evidence(evidence_id="E1", claim_id="C1", url="https://a.com/1", title="t", body_text=body)


def test_fabricated_quote_is_discarded():
    evidence = _evidence("회사는 오늘 입장문을 발표했다. 조사에 성실히 협조하겠다고 밝혔다.")
    gemini = FakeGemini(
        {"stance": "support", "confidence": 0.8, "relevant_quote": "임원이 직접 은폐를 지시했다고 자백했다", "reason": "r"}
    )
    result = analyze_stance(_claim(), evidence, gemini)
    assert result.relevant_quote == ""
    assert result.quote_verified is False


def test_intent_claim_without_direct_evidence_is_insufficient():
    evidence = _evidence("회사는 오늘 입장문을 발표했다. 조사에 성실히 협조하겠다고 밝혔다.")
    gemini = FakeGemini(
        {"stance": "support", "confidence": 0.9, "relevant_quote": "조사에 성실히 협조하겠다고 밝혔다", "reason": "r"}
    )
    result = analyze_stance(_claim(claim_type="intent"), evidence, gemini)
    assert result.stance.value == "insufficient"


def test_real_quote_is_kept():
    evidence = _evidence("회사는 오늘 입장문을 발표했다. 조사에 성실히 협조하겠다고 밝혔다.")
    gemini = FakeGemini(
        {"stance": "mixed", "confidence": 0.6, "relevant_quote": "조사에 성실히 협조하겠다고 밝혔다", "reason": "r"}
    )
    result = analyze_stance(_claim(claim_type="event"), evidence, gemini)
    assert result.quote_verified is True
    assert result.relevant_quote != ""


def test_analyze_stances_batches_multiple_evidences_into_one_call():
    evidences = [_evidence("첫 번째 자료 본문"), Evidence(evidence_id="E2", claim_id="C1", url="https://b.com/2", title="t2", body_text="두 번째 자료 본문")]
    gemini = FakeGemini(
        [
            {"id": "E1", "stance": "support", "confidence": 0.7, "relevant_quote": "첫 번째 자료 본문", "reason": "r"},
            {"id": "E2", "stance": "refute", "confidence": 0.6, "relevant_quote": "두 번째 자료 본문", "reason": "r"},
        ]
    )
    results = analyze_stances(_claim(claim_type="event"), evidences, gemini)

    assert gemini.calls == 1
    by_id = {r.evidence_id: r for r in results}
    assert by_id["E1"].stance.value == "support"
    assert by_id["E2"].stance.value == "refute"
