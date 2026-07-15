"""AI가 제시한 인용문이 실제 본문/snippet에 존재하는지 코드로 검증한다."""
from __future__ import annotations

import re


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[\"'“”‘’.,·…\-–—]", "", text)
    return text


def quote_exists_in_text(quote: str, source_text: str) -> bool:
    """정규화 후 부분 문자열 매칭. 공백/문장부호 차이는 허용하되 새로운 문장 생성은 막는다."""
    if not quote or not source_text:
        return False
    normalized_quote = _normalize(quote)
    normalized_source = _normalize(source_text)
    if len(normalized_quote) < 4:
        return False
    if normalized_quote in normalized_source:
        return True

    # RapidFuzz로 근사 매칭 (긴 본문에서 문장 단위 유사도 검사)
    try:
        from rapidfuzz import fuzz

        window = len(normalized_quote)
        if window == 0 or len(normalized_source) < window:
            return False
        step = max(1, window // 2)
        best = 0
        for i in range(0, len(normalized_source) - window + 1, step):
            segment = normalized_source[i : i + window]
            score = fuzz.ratio(normalized_quote, segment)
            best = max(best, score)
            if best >= 95:
                return True
        return best >= 95
    except Exception:
        return False
