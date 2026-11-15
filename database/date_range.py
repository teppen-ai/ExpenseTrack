"""Date-range validation and quick-select presets for the profile filter.

Pure Python: nothing here touches SQLite.
"""

import calendar
from datetime import date, datetime

DATE_FORMAT_ERROR = "date must use the YYYY-MM-DD format."
RANGE_ORDER_ERROR = "Start date must be on or before end date."


def _parse_date(raw):
    """Return an ISO date string for a YYYY-MM-DD value, else None."""
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        return None


def _months_ago(today, months):
    """Return the date ``months`` calendar months before today (day clamped)."""
    index = today.year * 12 + today.month - 1 - months
    year, month = divmod(index, 12)
    month += 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _date_presets(today, start=None, end=None):
    """Return the quick-select ranges, flagging the one matching start/end."""
    month_end = today.replace(
        day=calendar.monthrange(today.year, today.month)[1]
    )
    ranges = [
        ("This Month", today.replace(day=1), month_end),
        ("Last 3 Months", _months_ago(today, 3), today),
        ("Last 6 Months", _months_ago(today, 6), today),
    ]
    return [
        {
            "label": label,
            "start": first.isoformat(),
            "end": last.isoformat(),
            "active": (first.isoformat(), last.isoformat()) == (start, end),
        }
        for label, first, last in ranges
    ]


def _validate_range(start_raw, end_raw):
    """Return (start, end, error) from raw query values.

    An invalid bound is dropped and reported; a valid bound is kept. If start
    is after end both bounds are dropped and reported.
    """
    start = _parse_date(start_raw) if start_raw else None
    end = _parse_date(end_raw) if end_raw else None

    bad = []
    if start_raw and start is None:
        bad.append("Start")
    if end_raw and end is None:
        bad.append("End")
    error = f"{' and '.join(bad)} {DATE_FORMAT_ERROR}" if bad else None

    if start and end and start > end:
        return start, end, RANGE_ORDER_ERROR
    return start, end, error


def resolve_date_filter(start_raw, end_raw, today=None):
    """Validate raw start/end query values and describe the resulting filter.

    Returns a dict with ``start``/``end`` (ISO dates to query with, or None),
    ``start_input``/``end_input`` (values to prefill the form), ``active``,
    ``error`` and ``presets``.
    """
    today = today or date.today()
    start, end, error = _validate_range(
        (start_raw or "").strip(), (end_raw or "").strip()
    )
    start_input, end_input = start or "", end or ""
    if error == RANGE_ORDER_ERROR:
        # Keep what the user typed in the form, but apply no filter.
        start = end = None

    return {
        "start": start,
        "end": end,
        "start_input": start_input,
        "end_input": end_input,
        "active": bool(start or end),
        "error": error,
        "presets": _date_presets(today, start, end),
    }
