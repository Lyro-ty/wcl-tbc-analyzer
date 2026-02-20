from datetime import UTC, datetime


def ensure_utc(dt: datetime) -> datetime:
    """Attach UTC timezone if naive, return as-is if already aware."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
