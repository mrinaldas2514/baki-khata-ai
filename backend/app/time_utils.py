"""Timezone helpers. All timestamps are stored and returned in UTC."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_utc(value: datetime, local_tz: ZoneInfo) -> datetime:
    """Convert to aware UTC. A naive datetime is treated as the shop's local time."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=local_tz)
    return value.astimezone(UTC)


def local_day_bounds(now: datetime, local_tz: ZoneInfo) -> tuple[date, datetime, datetime]:
    """Return (local date, start in UTC, end in UTC) of the local day containing `now`."""
    local_date = now.astimezone(local_tz).date()
    start = datetime.combine(local_date, time.min, tzinfo=local_tz)
    end = start + timedelta(days=1)
    return local_date, start.astimezone(UTC), end.astimezone(UTC)
