"""후속 질문 정확히 3개를 생성한다 (스펙 19장). 근거 부족/상충/누락 통계·기간·비교 맥락을 우선한다."""
from __future__ import annotations

from ..providers.base import TextLLMProvider
from ..schemas import ClaimVerdict

PROMPT_TEMPLATE = """아래 판정 결과를 참고해서 사용자가 이어서 물어볼 만한 후속 질문을 정확히 3개 만들어라.
다음을 우선순위로 삼아라: 1) 근거가 부족한 부분 2) 자료가 충돌하는 부분 3) 빠진 통계·기간·비교 맥락.

{verdict_lines}

JSON 배열로만 응답: ["질문1", "질문2", "질문3"]
"""


def generate_followups(verdicts: list[ClaimVerdict], gemini: TextLLMProvider) -> list[str]:
    fallback = _fallback_questions(verdicts)
    if not gemini.is_configured():
        return fallback

    lines = "\n".join(
        f"- {v.claim_text} → {v.status.value} / 부족한 점: {', '.join(v.insufficient_points) or '없음'}"
        for v in verdicts
    )
    raw = gemini.generate_json(PROMPT_TEMPLATE.format(verdict_lines=lines))
    questions = [q for q in raw if isinstance(q, str)] if isinstance(raw, list) else []

    if len(questions) < 3:
        questions.extend(fallback)
    return questions[:3]


_GENERIC_FALLBACKS = [
    "이 주제와 관련해 최신 통계나 기간별 비교 자료가 있나요?",
    "추가로 확인할 만한 공식 자료가 있나요?",
    "이 주제에 대한 다른 관점의 보도가 있나요?",
    "관련 통계나 기간별 변화는 어떻게 되나요?",
]


def _fallback_questions(verdicts: list[ClaimVerdict]) -> list[str]:
    questions: list[str] = []
    for v in verdicts:
        if v.insufficient_points:
            questions.append(f"'{v.claim_text[:30]}'에 대해 어떤 추가 자료가 있으면 검증이 가능할까요?")
        if v.score.source_conflict >= 0.2:
            questions.append(f"'{v.claim_text[:30]}'와 관련해 상충하는 자료들은 어떤 차이가 있나요?")

    for generic in _GENERIC_FALLBACKS:
        if len(questions) >= 3:
            break
        if generic not in questions:
            questions.append(generic)

    return questions[:3]
