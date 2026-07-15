"""전체 판정을 종합한 요약을 생성한다."""
from __future__ import annotations

from ..providers.gemini_provider import GeminiProvider
from ..schemas import ClaimVerdict

PROMPT_TEMPLATE = """다음은 한 게시물/기사에서 추출한 주장들의 검증 결과다. 사용자에게 보여줄 종합 설명을 3~5문장으로
작성하라. 어디까지 확인되었고 어디부터 추측/해석인지 명확히 구분하라. 절대적 단정 표현("확실히 거짓이다" 등)을
피하고 "공개된 자료 기준"이라는 점을 드러내라.

{verdict_lines}
"""


def generate_summary(verdicts: list[ClaimVerdict], gemini: GeminiProvider) -> str:
    if not verdicts:
        return "분석할 주장을 찾지 못했습니다."

    lines = "\n".join(
        f"- {v.claim_text} → 판정: {v.status.value} / {v.confidence_label} / {v.verification_scope}"
        for v in verdicts
    )

    if not gemini.is_configured():
        return (
            "Gemini 미설정으로 자동 요약을 생성할 수 없습니다. 아래 각 주장별 판정을 참고하세요.\n" + lines
        )

    text = gemini.generate_text(PROMPT_TEMPLATE.format(verdict_lines=lines))
    return text or ("요약 생성에 실패했습니다. 아래 각 주장별 판정을 참고하세요.\n" + lines)
