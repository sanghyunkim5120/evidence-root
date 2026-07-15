"""자료 발행일(published_at) 파싱과 최신성 가중치 계산. 여러 공급자가 서로 다른 날짜 형식을 준다
(네이버 뉴스는 RFC822 pubDate, 블로그/카페는 8자리 숫자 postdate, 본문 스크래핑은 ISO 계열)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

_YMD_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def parse_published_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()

    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass

    if re.fullmatch(r"\d{8}", raw):
        try:
            return datetime.strptime(raw, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    try:
        dt = datetime.fromisoformat(raw[:19])
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    match = _YMD_RE.match(raw)
    if match:
        try:
            y, m, d = (int(g) for g in match.groups())
            return datetime(y, m, d, tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


def recency_weight(raw: str | None, reference: datetime | None = None) -> float:
    """최신 자료일수록 1.0에 가깝게, 오래될수록 감쇠시킨다. 날짜를 알 수 없으면 중간값(0.7)을 준다
    (전혀 반영 안 하는 것보다는 낫지만, 최신임이 확인된 자료보다는 낮게 취급)."""
    dt = parse_published_at(raw)
    if dt is None:
        return 0.7

    ref = reference or datetime.now(timezone.utc)
    age_days = max(0, (ref - dt).days)

    if age_days <= 30:
        return 1.0
    if age_days <= 180:
        return 0.85
    if age_days <= 365:
        return 0.6
    return 0.4
