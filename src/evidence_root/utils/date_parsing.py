"""자료 발행일(published_at) 파싱과 최신성 가중치 계산. 여러 공급자가 서로 다른 날짜 형식을 준다
(네이버 뉴스는 RFC822 pubDate, 블로그/카페는 8자리 숫자 postdate, 본문 스크래핑은 ISO 계열)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

_YMD_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
# 주장 추출 단계에서 LLM이 "2026년 3월", "2026년 3월 15일", "2026년" 같은 자연어 날짜를 준다.
_KOREAN_DATE_RE = re.compile(r"(\d{4})\s*년(?:\s*(\d{1,2})\s*월(?:\s*(\d{1,2})\s*일)?)?")


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

    match = _KOREAN_DATE_RE.search(raw)
    if match:
        y = int(match.group(1))
        m = int(match.group(2)) if match.group(2) else 1
        d = int(match.group(3)) if match.group(3) else 1
        try:
            return datetime(y, m, d, tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


def recency_weight(raw: str | None, reference: datetime | None = None, event_date: datetime | None = None) -> float:
    """자료가 검증 대상 사건 시점에 얼마나 가까운지로 가중치를 매긴다.

    "오늘로부터 얼마나 오래됐나"가 아니라 "그 사건이 일어난 시점으로부터 얼마나 떨어져 있나"가
    기준이다. 사건 날짜(event_date, 주장에서 추출된 dates)를 알면 그걸 기준점으로 쓰고, 모르면
    reference(기본값 현재 시각)로 대체한다.

    - 사건 발생 이전에 나온 자료는 이 사건 자체를 다룰 수 없으므로(아직 안 일어난 일이라) 낮은 가중치
    - 사건 발생 직후~한 달 이내 보도는 가장 신뢰도 높은 동시대 보도로 최고 가중치
    - 시간이 지날수록(후속 보도·회고성 기사) 점진적으로 가중치가 낮아짐
    - 날짜를 알 수 없으면 중간값(0.7)
    """
    dt = parse_published_at(raw)
    if dt is None:
        return 0.7

    anchor = event_date or reference or datetime.now(timezone.utc)
    delta_days = (dt - anchor).days  # 양수 = 사건/기준 시점 이후에 나온 자료

    # "사건 발생 전 자료라 다룰 수 없다"는 판단은 실제 사건 날짜를 알 때만 의미가 있다. reference로
    # 대체된 경우("오늘" 등) 과거 자료인 건 지극히 정상이므로 이 페널티를 적용하지 않는다.
    if event_date is not None and delta_days < -7:
        return 0.3

    distance = abs(delta_days)
    if distance <= 30:
        return 1.0
    if distance <= 180:
        return 0.85
    if distance <= 365:
        return 0.6
    return 0.4
