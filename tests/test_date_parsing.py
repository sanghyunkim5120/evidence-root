from datetime import datetime, timezone

from evidence_root.utils.date_parsing import parse_published_at, recency_weight


def test_parses_rfc822_naver_news_format():
    dt = parse_published_at("Wed, 15 Jul 2026 10:00:00 +0900")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 7 and dt.day == 15


def test_parses_eight_digit_postdate():
    dt = parse_published_at("20260710")
    assert dt is not None
    assert (dt.year, dt.month, dt.day) == (2026, 7, 10)


def test_parses_dotted_date():
    dt = parse_published_at("2026.07.10")
    assert (dt.year, dt.month, dt.day) == (2026, 7, 10)


def test_unknown_format_returns_none():
    assert parse_published_at("모름") is None
    assert parse_published_at(None) is None


def test_recent_article_gets_full_weight():
    ref = datetime(2026, 7, 15, tzinfo=timezone.utc)
    weight = recency_weight("20260710", reference=ref)
    assert weight == 1.0


def test_old_article_gets_decayed_weight():
    ref = datetime(2026, 7, 15, tzinfo=timezone.utc)
    weight = recency_weight("20230101", reference=ref)
    assert weight == 0.4


def test_missing_date_gets_middle_weight():
    assert recency_weight(None) == 0.7


def test_parses_korean_year_month_day():
    dt = parse_published_at("2026년 3월 15일")
    assert (dt.year, dt.month, dt.day) == (2026, 3, 15)


def test_parses_korean_year_month_only():
    dt = parse_published_at("2026년 3월")
    assert (dt.year, dt.month, dt.day) == (2026, 3, 1)


def test_article_published_right_at_old_event_gets_full_weight():
    """오늘(2026-07-15) 기준으로는 3년 전 자료라 낡아 보여도, 그 사건이 실제로 일어난 시점(2023년 3월)에
    맞춰 바로 보도된 기사라면 가장 신뢰도 높은 동시대 보도로 취급해야 한다."""
    event_date = datetime(2023, 3, 1, tzinfo=timezone.utc)
    weight = recency_weight("20230305", event_date=event_date)
    assert weight == 1.0


def test_article_published_before_event_gets_low_weight():
    """사건이 일어나기 훨씬 전에 나온 자료는 이 사건을 다룰 수 없다."""
    event_date = datetime(2026, 6, 1, tzinfo=timezone.utc)
    weight = recency_weight("20260101", event_date=event_date)
    assert weight == 0.3


def test_article_long_after_event_decays_relative_to_event_not_today():
    event_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    weight = recency_weight("20210601", event_date=event_date)  # 사건 1년 5개월 뒤 후속 보도
    assert weight == 0.4
