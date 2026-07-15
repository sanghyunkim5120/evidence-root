from evidence_root.schemas import Claim, ClaimScore, ClaimVerdict
from evidence_root.services.followup_generator import generate_followups


class UnconfiguredGemini:
    def is_configured(self):
        return False


class ConfiguredGemini:
    def __init__(self, response):
        self._response = response

    def is_configured(self):
        return True

    def generate_json(self, prompt, system=None):
        return self._response


def _verdict():
    return ClaimVerdict(
        claim_id="C1", claim_text="테스트 주장", claim_type="event", status="insufficient_evidence",
        confidence_label="낮음", verification_scope="독립 근거 0건",
        insufficient_points=["근거 부족"], score=ClaimScore(claim_id="C1"),
    )


def test_exactly_three_questions_without_gemini():
    questions = generate_followups([_verdict()], UnconfiguredGemini())
    assert len(questions) == 3


def test_exactly_three_questions_when_gemini_returns_too_few():
    gemini = ConfiguredGemini(["질문 하나만 왔을 때"])
    questions = generate_followups([_verdict()], gemini)
    assert len(questions) == 3


def test_exactly_three_questions_when_gemini_returns_too_many():
    gemini = ConfiguredGemini(["q1", "q2", "q3", "q4", "q5"])
    questions = generate_followups([_verdict()], gemini)
    assert len(questions) == 3
