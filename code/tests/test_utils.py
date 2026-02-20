from datetime import UTC, datetime, timezone

from shukketsu.utils import ensure_utc


def test_naive_datetime_gets_utc():
    naive = datetime(2026, 1, 15, 12, 0, 0)
    result = ensure_utc(naive)
    assert result.tzinfo is UTC
    assert result.year == 2026
    assert result.month == 1
    assert result.day == 15


def test_aware_datetime_passthrough():
    aware = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
    result = ensure_utc(aware)
    assert result is aware


def test_non_utc_aware_datetime_passthrough():
    eastern = timezone(offset=datetime.resolution * -5 * 3600)
    aware = datetime(2026, 1, 15, 12, 0, 0, tzinfo=eastern)
    result = ensure_utc(aware)
    assert result is aware
    assert result.tzinfo is eastern
