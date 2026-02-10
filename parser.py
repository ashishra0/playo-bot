import re
from datetime import date, timedelta

from models import SearchParams

# Recognized keyword arguments
_KEYWORDS = {"area", "date", "time", "sport", "city"}

_TIME_RE = re.compile(
    r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$",
    re.IGNORECASE,
)

_TIME_24_RE = re.compile(r"^(\d{1,2}):(\d{2})$")

_WEEKDAYS = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Matches "feb10", "feb 10", "10feb", "10 feb" — handled as two-token below
_MONTH_DAY_RE = re.compile(
    r"^([a-z]+)\s*(\d{1,2})$",
    re.IGNORECASE,
)
_DAY_MONTH_RE = re.compile(
    r"^(\d{1,2})\s*([a-z]+)$",
    re.IGNORECASE,
)


def _normalize_time(raw: str) -> str:
    """Convert a time string to HH:MM (24h). Accepts '7pm', '7:30pm', '19:30'."""
    m = _TIME_RE.match(raw.strip())
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        period = m.group(3).lower()
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Invalid time: {raw}")
        return f"{hour:02d}:{minute:02d}"

    m = _TIME_24_RE.match(raw.strip())
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Invalid time: {raw}")
        return f"{hour:02d}:{minute:02d}"

    raise ValueError(
        f"Cannot parse time '{raw}'. Use formats like 7pm, 7:30pm, or 19:30."
    )


def _normalize_date(raw: str) -> str:
    """Convert a date string to YYYY-MM-DD.

    Accepts: today, tomorrow, mon-sun, feb10, 10feb, feb 10, 2026-02-10
    """
    lower = raw.strip().lower()
    today = date.today()

    if lower == "today":
        return today.isoformat()
    if lower == "tomorrow":
        return (today + timedelta(days=1)).isoformat()

    # Weekday names: next occurrence (today if matches)
    if lower in _WEEKDAYS:
        target = _WEEKDAYS[lower]
        days_ahead = (target - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 0  # today
        return (today + timedelta(days=days_ahead)).isoformat()

    # "feb10" / "10feb" (single token, no space)
    m = _MONTH_DAY_RE.match(raw.strip())
    if m and m.group(1).lower() in _MONTHS:
        month = _MONTHS[m.group(1).lower()]
        day = int(m.group(2))
        return _resolve_month_day(month, day, today)

    m = _DAY_MONTH_RE.match(raw.strip())
    if m and m.group(2).lower() in _MONTHS:
        month = _MONTHS[m.group(2).lower()]
        day = int(m.group(1))
        return _resolve_month_day(month, day, today)

    # YYYY-MM-DD
    try:
        parsed = date.fromisoformat(raw.strip())
        return parsed.isoformat()
    except ValueError:
        pass

    raise ValueError(
        f"Cannot parse date '{raw}'. "
        "Use: today, tomorrow, mon-sun, feb10, 10feb, or YYYY-MM-DD."
    )


def _resolve_month_day(month: int, day: int, today: date) -> str:
    """Build a date from month+day, using current or next year."""
    year = today.year
    try:
        d = date(year, month, day)
    except ValueError as exc:
        raise ValueError(f"Invalid date: {month}/{day}") from exc
    if d < today:
        d = date(year + 1, month, day)
    return d.isoformat()


def _looks_like_time(token: str) -> bool:
    return bool(_TIME_RE.match(token)) or bool(_TIME_24_RE.match(token))


def _looks_like_date(token: str) -> bool:
    lower = token.lower()
    if lower in ("today", "tomorrow"):
        return True
    if lower in _WEEKDAYS:
        return True
    if re.match(r"^\d{4}-\d{2}-\d{2}$", token):
        return True
    m = _MONTH_DAY_RE.match(token)
    if m and m.group(1).lower() in _MONTHS:
        return True
    m = _DAY_MONTH_RE.match(token)
    if m and m.group(2).lower() in _MONTHS:
        return True
    return False


def parse_find_args(text: str) -> SearchParams:
    """Parse /find command arguments.

    Supports three styles (and mixes):
      Positional:  /find koramangala 7pm tomorrow
      Key-value:   /find area=koramangala time=7pm date=tomorrow
      Mixed:       /find koramangala time=7pm
    """
    text = text.strip()
    if not text:
        raise ValueError(
            "Please provide at least an area.\n"
            "Example: /find koramangala 7pm tomorrow"
        )

    tokens = text.split()

    area_parts: list[str] = []
    time_raw: str | None = None
    date_raw: str | None = None

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Key=value form
        if "=" in token:
            key, _, value = token.partition("=")
            key = key.lower()
            if key not in _KEYWORDS:
                raise ValueError(f"Unknown parameter '{key}'. Known: {', '.join(sorted(_KEYWORDS))}")
            if not value:
                raise ValueError(f"Missing value for '{key}'.")
            if key == "area":
                area_parts.append(value)
            elif key == "time":
                time_raw = value
            elif key == "date":
                date_raw = value
            # city and sport handled by bot.py / ignored
            i += 1
            continue

        # Positional: detect time or date by pattern
        if _looks_like_time(token) and time_raw is None:
            time_raw = token
        elif _looks_like_date(token) and date_raw is None:
            date_raw = token
        elif (
            token.lower() in _MONTHS
            and date_raw is None
            and i + 1 < len(tokens)
            and tokens[i + 1].isdigit()
        ):
            # Two-token date: "feb 10"
            date_raw = token + tokens[i + 1]
            i += 1
        elif (
            token.isdigit()
            and date_raw is None
            and i + 1 < len(tokens)
            and tokens[i + 1].lower() in _MONTHS
        ):
            # Two-token date: "10 feb"
            date_raw = token + tokens[i + 1]
            i += 1
        else:
            area_parts.append(token)

        i += 1

    area = " ".join(area_parts)
    if not area:
        raise ValueError(
            "Could not determine the area. Provide it as the first argument.\n"
            "Example: /find koramangala 7pm tomorrow"
        )

    params = SearchParams(area=area)
    if time_raw:
        params.time = _normalize_time(time_raw)
    if date_raw:
        params.date = _normalize_date(date_raw)

    return params
