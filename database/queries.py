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


def get_summary_stats(user_id):
    """Return total_spent, transaction_count and top_category for a user."""
    with closing(get_db()) as conn:
        total, count = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id,),
        ).fetchone()
    return {
        "total_spent": float(total),
        "transaction_count": count,
        "top_category": top["category"] if top else EMPTY_VALUE,
    }


def get_recent_transactions(user_id, limit=10):
    """Return a user's latest expenses, newest first."""
    with closing(get_db()) as conn:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, int(limit)),
        ).fetchall()
    return [
        {
            "date": row["date"],
            "description": row["description"] or "",
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]


def get_category_breakdown(user_id):
    """Return per-category totals with whole-number percents summing to 100."""
    with closing(get_db()) as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category "
            "ORDER BY total DESC, category ASC",
            (user_id,),
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
