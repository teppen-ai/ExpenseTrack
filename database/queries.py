"""Read-only query helpers for the profile page."""

from contextlib import closing
from datetime import datetime

from database.db import get_db, get_user_by_id

EMPTY_VALUE = "—"


def _initials(name):
    parts = name.split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _member_since(created_at):
    try:
        return datetime.strptime(created_at[:10], "%Y-%m-%d").strftime("%B %Y")
    except (TypeError, ValueError):
        return EMPTY_VALUE


def get_profile_user(user_id):
    """Return name, email, initials and member_since for a user, or None."""
    user = get_user_by_id(user_id)
    if user is None:
        return None
    return {
        "name": user["name"],
        "email": user["email"],
        "initials": _initials(user["name"]),
        "member_since": _member_since(user["created_at"]),
    }


# Static clause: a NULL bound means "no limit", so no SQL is built dynamically.
_EXPENSE_FILTER = (
    "user_id = ? AND (? IS NULL OR date >= ?) AND (? IS NULL OR date <= ?)"
)


def _filter_params(user_id, start, end):
    """Return the values for ``_EXPENSE_FILTER``, in placeholder order."""
    return (user_id, start, start, end, end)


def get_summary_stats(user_id, start=None, end=None):
    """Return total_spent, transaction_count and top_category for a user."""
    params = _filter_params(user_id, start, end)
    with closing(get_db()) as conn:
        total, count = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses WHERE "
            + _EXPENSE_FILTER,
            params,
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE "
            + _EXPENSE_FILTER
            + " GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            params,
        ).fetchone()
    return {
        "total_spent": float(total),
        "transaction_count": count,
        "top_category": top["category"] if top else EMPTY_VALUE,
    }


def get_recent_transactions(user_id, limit=10, *, start=None, end=None):
    """Return a user's latest expenses in the date range, newest first."""
    params = _filter_params(user_id, start, end)
    with closing(get_db()) as conn:
        rows = conn.execute(
            "SELECT id, date, description, category, amount FROM expenses WHERE "
            + _EXPENSE_FILTER
            + " ORDER BY date DESC, id DESC LIMIT ?",
            (*params, int(limit)),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "date": row["date"],
            "description": row["description"] or "",
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]


def get_category_breakdown(user_id, start=None, end=None):
    """Return per-category totals with whole-number percents summing to 100."""
    params = _filter_params(user_id, start, end)
    with closing(get_db()) as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses WHERE "
            + _EXPENSE_FILTER
            + " GROUP BY category "
            "ORDER BY total DESC, category ASC",
            params,
        ).fetchall()
    grand_total = sum(row["total"] for row in rows)
    if not rows or grand_total <= 0:
        return []
    breakdown = [
        {
            "category": row["category"],
            "total": round(row["total"], 2),
            "percent": round(row["total"] * 100 / grand_total),
        }
        for row in rows
    ]
    remainder = 100 - sum(item["percent"] for item in breakdown)
    breakdown[0]["percent"] = max(0, breakdown[0]["percent"] + remainder)
    return breakdown
