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
