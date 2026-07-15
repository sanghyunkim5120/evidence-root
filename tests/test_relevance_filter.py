from evidence_root.schemas import Claim, Evidence
from evidence_root.services.relevance_filter import gemini_relevance_check, prefilter_relevance


def _claim():
    return Claim(
        claim_id="C1",
        claim_text="서울시는 2024년 청년 지원 예산을 300억원 편성했다",
        claim_type="numerical",
        checkability="checkable",
        keywords=["서울시", "청년 지원 예산", "300억원"],
    )


def test_unrelated_evidence_is_excluded():
    claim = _claim()
    evidences = [
        Evidence(
            evidence_id="E1", claim_id="C1", url="https://a.com/1",
            title="서울시, 청년 지원 예산 300억원 편성", snippet="서울시는 2024년 청년 지원 예산으로 300억원을 편성했다고 밝혔다.",
        ),
        Evidence(
            evidence_id="E2", claim_id="C1", url="https://b.com/2",
            title="부산 앞바다서 유조선 충돌 사고", snippet="부산 해경은 오늘 새벽 유조선 두 척이 충돌하는 사고가 발생했다고 밝혔다.",
        ),
    ]
    kept = prefilter_relevance(claim, evidences, threshold=0.35)
    kept_ids = {e.evidence_id for e in kept}
    assert "E1" in kept_ids
    assert "E2" not in kept_ids


class FakeGemini:
    def __init__(self, response):
        self._response = response
        self.calls = 0

    def is_configured(self):
        return True

    def generate_json(self, prompt, system=None):
        self.calls += 1
        return self._response


def test_gemini_relevance_check_batches_all_evidences_in_one_call():
    claim = _claim()
    evidences = [
        Evidence(evidence_id="E1", claim_id="C1", url="https://a.com/1", title="t1", body_text="관련 있음"),
        Evidence(evidence_id="E2", claim_id="C1", url="https://b.com/2", title="t2", body_text="관련 없음"),
    ]
    gemini = FakeGemini([{"id": "E1", "relevant": True}, {"id": "E2", "relevant": False}])

    kept = gemini_relevance_check(claim, evidences, gemini)

    assert gemini.calls == 1
    assert {e.evidence_id for e in kept} == {"E1"}
