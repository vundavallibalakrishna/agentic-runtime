"""Cron preview. Spec 15 §5 returns the next five fires."""

import itertools
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

PREVIEW_COUNT = 5
_DAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


def preview_schedule(cron: str, timezone: str, *, count: int = PREVIEW_COUNT) -> dict[str, object]:
    """Return whether a cron expression is valid and its next fires."""
    zone = _zone(timezone)
    if zone is None:
        return {"valid": False, "description": "", "next": []}
    if not croniter.is_valid(cron):
        return {"valid": False, "description": "", "next": []}
    cursor = croniter(cron, datetime.now(zone))
    fires = [cursor.get_next(datetime).isoformat() for _ in range(count)]
    return {"valid": True, "description": describe_cron(cron, timezone), "next": fires}


def min_gap_seconds(cron: str, timezone: str) -> int | None:
    """Smallest gap in the next day of fires, or None when the cron is invalid."""
    found = preview_schedule(cron, timezone, count=8)
    nxt = found["next"]
    if not isinstance(nxt, list) or len(nxt) < 2:
        return None
    moments = [datetime.fromisoformat(str(item)) for item in nxt]
    gaps = ((right - left).total_seconds() for left, right in itertools.pairwise(moments))
    return int(min(gaps))


def next_fire(cron: str, timezone: str, after: datetime | None = None) -> datetime | None:
    """The first fire strictly after ``after``."""
    zone = _zone(timezone)
    if zone is None:
        return None
    if not croniter.is_valid(cron):
        return None
    start = after.astimezone(zone) if after is not None else datetime.now(zone)
    found = croniter(cron, start).get_next(datetime)
    return found if isinstance(found, datetime) else None


def describe_cron(cron: str, timezone: str) -> str:
    """A short sentence for the common weekly and daily forms."""
    parts = cron.split()
    label = _tz_label(timezone)
    if len(parts) == 5 and parts[0].isdigit() and parts[1].isdigit() and parts[2:4] == ["*", "*"]:
        hour = int(parts[1])
        minute = int(parts[0])
        clock = f"{hour:02d}:{minute:02d}"
        if parts[4] == "*":
            return f"Every day {clock} {label}".strip()
        if parts[4].isdigit():
            day = _DAYS[int(parts[4]) % 7]
            return f"Every {day} {clock} {label}".strip()
    return f"{cron} ({timezone})"


def _zone(timezone: str) -> ZoneInfo | None:
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return None
    except ValueError:
        return None


def _tz_label(timezone: str) -> str:
    if timezone == "Asia/Kolkata":
        return "IST"
    try:
        offset = datetime.now(ZoneInfo(timezone)).utcoffset() or timedelta(0)
    except ZoneInfoNotFoundError, ValueError:
        return timezone
    hours = int(offset.total_seconds() // 3600)
    return f"UTC{hours:+d}" if hours else "UTC"
