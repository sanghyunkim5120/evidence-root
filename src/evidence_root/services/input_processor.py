"""사용자가 입력한 문장을 분석 파이프라인 입력 텍스트로 정규화한다."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InputBundle:
    input_text: str
    source_kind: str = "text"


def process_text_input(text: str) -> InputBundle:
    return InputBundle(input_text=text.strip())
