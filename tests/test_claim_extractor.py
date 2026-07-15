from evidence_root.services.claim_extractor import extract_claims


class FakeGemini:
    def __init__(self, response):
        self._response = response

    def is_configured(self):
        return True

    def generate_json(self, prompt, system=None):
        return self._response


def test_complex_sentence_splits_into_multiple_claims():
    response = [
        {
            "claim_id": "C1", "claim_text": "정부는 15일 예산 300억원을 편성했다고 발표했다.",
            "claim_type": "numerical", "checkability": "checkable", "keywords": ["정부", "예산"],
        },
        {
            "claim_id": "C2", "claim_text": "이 정책은 매우 잘못된 결정이다.",
            "claim_type": "other", "checkability": "opinion", "keywords": [],
        },
        {
            "claim_id": "C3", "claim_text": "정책 발표 직후 여론이 크게 반발했다.",
            "claim_type": "event", "checkability": "checkable", "keywords": ["여론", "반발"],
        },
    ]
    gemini = FakeGemini(response)
    claims = extract_claims("정부는 15일 예산 300억원을 편성했다고 발표했다. 이 정책은 매우 잘못된 결정이다. 정책 발표 직후 여론이 크게 반발했다.", gemini)

    assert len(claims) == 3
    assert claims[0].checkability.value == "checkable"
    assert claims[1].checkability.value == "opinion"


def test_max_three_claims_enforced():
    response = [
        {"claim_id": f"C{i}", "claim_text": f"주장{i}", "claim_type": "event", "checkability": "checkable"}
        for i in range(1, 6)
    ]
    gemini = FakeGemini(response)
    claims = extract_claims("여러 사건을 나열한 긴 문장", gemini, max_claims=3)
    assert len(claims) == 3


def test_swapped_claim_type_and_checkability_is_corrected_not_dropped():
    response = [
        {
            "claim_id": "C1", "claim_text": "이 정책은 매우 잘못된 결정이다.",
            "claim_type": "opinion", "checkability": "checkable", "keywords": [],
        },
    ]
    gemini = FakeGemini(response)
    claims = extract_claims("이 정책은 매우 잘못된 결정이다.", gemini)

    assert len(claims) == 1
    assert claims[0].claim_type.value == "other"


def test_gemini_not_configured_returns_empty():
    class Unconfigured:
        def is_configured(self):
            return False

    assert extract_claims("아무 문장", Unconfigured()) == []
