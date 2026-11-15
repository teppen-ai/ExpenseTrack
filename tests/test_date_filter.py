"""Tests for feature 06-date-filter: inclusive date-range filter on /profile."""

import re
from contextlib import closing
from datetime import date

import pytest

from database import db
from database.date_range import resolve_date_filter
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

DEMO_EMAIL = "demo@expensetrack.com"
DEMO_PASSWORD = "demo123"
PINNED_TODAY = date(2026, 11, 15)
EMPTY = "—"


# --------------------------------------------------------------------------
# Helpers and fixtures
# --------------------------------------------------------------------------


def _insert_expenses(user_id, rows):
    """rows: iterable of (amount, category, iso_date, description)."""
    with closing(db.get_db()) as conn, conn:
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [(user_id, a, c, d, desc) for a, c, d, desc in rows],
        )


def _month_day(day):
    today = date.today()
    return date(today.year, today.month, day).isoformat()


def _profile_path(client):
    return client.app.url_path_for("profile")


def _login_path(client):
    return client.app.url_path_for("login")


@pytest.fixture
def empty_db(temp_db):
    """Initialised DB without seed data."""
    db.init_db()
    return temp_db


@pytest.fixture
def user_id(empty_db):
    return db.create_user("Filter User", "filter@example.com", "secret123")


@pytest.fixture
def other_user_id(empty_db):
    return db.create_user("Other User", "other@example.com", "secret123")


@pytest.fixture
def demo_id(client):
    return db.get_user_by_email(DEMO_EMAIL)["id"]


@pytest.fixture
def auth_client(client):
    response = client.post(
        client.app.url_path_for("login"),
        content=f"email={DEMO_EMAIL}&password={DEMO_PASSWORD}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 303, "Login should redirect with 303"
    return client


def _get_profile(client, **params):
    return client.get(_profile_path(client), params=params)


def _row_count(html):
    return len(re.findall(r"<time datetime=", html))


# --------------------------------------------------------------------------
# resolve_date_filter (pure unit tests)
# --------------------------------------------------------------------------


class TestResolveDateFilter:
    @pytest.mark.parametrize("start,end", [(None, None), ("", ""), ("  ", None)])
    def test_resolve_blank_inputs_returns_inactive_filter(self, start, end):
        f = resolve_date_filter(start, end, today=PINNED_TODAY)
        assert f["start"] is None and f["end"] is None
        assert f["active"] is False
        assert f["error"] is None
        assert f["start_input"] == "" and f["end_input"] == ""

    def test_resolve_valid_range_is_active(self):
        f = resolve_date_filter("2026-11-01", "2026-11-15", today=PINNED_TODAY)
        assert f["start"] == "2026-11-01"
        assert f["end"] == "2026-11-15"
        assert f["start_input"] == "2026-11-01"
        assert f["end_input"] == "2026-11-15"
        assert f["active"] is True
        assert f["error"] is None

    def test_resolve_start_only_is_open_ended(self):
        f = resolve_date_filter("2026-11-01", None, today=PINNED_TODAY)
        assert f["start"] == "2026-11-01"
        assert f["end"] is None
        assert f["active"] is True

    def test_resolve_end_only_is_open_ended(self):
        f = resolve_date_filter("", "2026-11-15", today=PINNED_TODAY)
        assert f["start"] is None
        assert f["end"] == "2026-11-15"
        assert f["active"] is True

    def test_resolve_same_day_range_is_valid(self):
        f = resolve_date_filter("2026-11-05", "2026-11-05", today=PINNED_TODAY)
        assert f["error"] is None
        assert f["start"] == f["end"] == "2026-11-05"
        assert f["active"] is True

    @pytest.mark.parametrize(
        "bad", ["banana", "2026-02-30", "2026-13-01", "01/02/2026", "2026-11-1x"]
    )
    def test_resolve_invalid_start_sets_error_and_is_ignored(self, bad):
        f = resolve_date_filter(bad, None, today=PINNED_TODAY)
        assert f["error"], f"Expected an error for {bad!r}"
        assert f["start"] is None
        assert f["active"] is False

    @pytest.mark.parametrize("bad", ["banana", "2026-02-30"])
    def test_resolve_invalid_end_sets_error_and_is_ignored(self, bad):
        f = resolve_date_filter(None, bad, today=PINNED_TODAY)
        assert f["error"]
        assert f["end"] is None
        assert f["active"] is False

    def test_resolve_non_padded_date_is_normalised(self):
        f = resolve_date_filter("2026-2-3", "2026-11-5", today=PINNED_TODAY)
        assert f["start"] == "2026-02-03"
        assert f["end"] == "2026-11-05"
        assert f["error"] is None

    def test_resolve_start_after_end_errors_and_applies_no_filter(self):
        f = resolve_date_filter("2026-11-20", "2026-11-01", today=PINNED_TODAY)
        assert f["error"]
        assert f["start"] is None and f["end"] is None
        assert f["active"] is False

    def test_resolve_start_after_end_keeps_entered_values_in_inputs(self):
        f = resolve_date_filter("2026-11-20", "2026-11-01", today=PINNED_TODAY)
        assert f["start_input"] == "2026-11-20"
        assert f["end_input"] == "2026-11-01"

    def test_resolve_valid_start_with_invalid_end_keeps_start(self):
        f = resolve_date_filter("2026-11-01", "banana", today=PINNED_TODAY)
        assert f["error"]
        assert f["start"] == "2026-11-01"
        assert f["end"] is None
        assert f["active"] is True

    def test_resolve_invalid_start_with_valid_end_keeps_end(self):
        f = resolve_date_filter("banana", "2026-11-15", today=PINNED_TODAY)
        assert f["error"]
        assert f["start"] is None
        assert f["end"] == "2026-11-15"
        assert f["active"] is True

    def test_resolve_presets_have_expected_ranges(self):
        presets = resolve_date_filter(None, None, today=PINNED_TODAY)["presets"]
        by_label = {p["label"]: p for p in presets}
        assert by_label["This Month"]["start"] == "2026-11-01"
        assert by_label["This Month"]["end"] == "2026-11-30"
        assert by_label["Last 3 Months"]["start"] == "2026-08-15"
        assert by_label["Last 3 Months"]["end"] == "2026-11-15"
        assert by_label["Last 6 Months"]["start"] == "2026-05-15"
        assert by_label["Last 6 Months"]["end"] == "2026-11-15"

    def test_resolve_this_month_preset_in_december_ends_on_31st(self):
        presets = resolve_date_filter(None, None, today=date(2026, 12, 10))["presets"]
        month = next(p for p in presets if p["label"] == "This Month")
        assert (month["start"], month["end"]) == ("2026-12-01", "2026-12-31")

    @pytest.mark.parametrize(
        "today,expected_end",
        [(date(2024, 2, 10), "2024-02-29"), (date(2026, 2, 10), "2026-02-28")],
    )
    def test_resolve_this_month_preset_handles_leap_february(
        self, today, expected_end
    ):
        presets = resolve_date_filter(None, None, today=today)["presets"]
        month = next(p for p in presets if p["label"] == "This Month")
        assert month["end"] == expected_end

    def test_resolve_month_presets_cross_year_boundary(self):
        presets = resolve_date_filter(None, None, today=date(2026, 1, 10))["presets"]
        by_label = {p["label"]: p for p in presets}
        assert by_label["Last 3 Months"]["start"] == "2025-10-10"
        assert by_label["Last 6 Months"]["start"] == "2025-07-10"

    def test_resolve_month_presets_clamp_day_to_month_length(self):
        presets = resolve_date_filter(None, None, today=date(2026, 5, 31))["presets"]
        by_label = {p["label"]: p for p in presets}
        assert by_label["Last 3 Months"]["start"] == "2026-02-28"

    def test_resolve_six_month_preset_clamps_to_leap_day(self):
        presets = resolve_date_filter(None, None, today=date(2024, 8, 31))["presets"]
        by_label = {p["label"]: p for p in presets}
        assert by_label["Last 6 Months"]["start"] == "2024-02-29"
        assert by_label["Last 3 Months"]["start"] == "2024-05-31"

    def test_resolve_six_month_preset_clamps_in_non_leap_year(self):
        presets = resolve_date_filter(None, None, today=date(2026, 8, 31))["presets"]
        by_label = {p["label"]: p for p in presets}
        assert by_label["Last 6 Months"]["start"] == "2026-02-28"

    def test_resolve_month_presets_end_today_and_roll_over_year_in_march(self):
        presets = resolve_date_filter(None, None, today=date(2026, 3, 31))["presets"]
        by_label = {p["label"]: p for p in presets}
        assert by_label["Last 3 Months"]["start"] == "2025-12-31"
        assert by_label["Last 6 Months"]["start"] == "2025-09-30"
        assert by_label["Last 3 Months"]["end"] == "2026-03-31"
        assert by_label["Last 6 Months"]["end"] == "2026-03-31"

    def test_resolve_preset_labels_are_exactly_the_three_ranges(self):
        presets = resolve_date_filter(None, None, today=PINNED_TODAY)["presets"]
        assert [p["label"] for p in presets] == [
            "This Month",
            "Last 3 Months",
            "Last 6 Months",
        ]

    def test_resolve_marks_last_three_months_preset_active(self):
        f = resolve_date_filter("2026-08-15", "2026-11-15", today=PINNED_TODAY)
        assert [p["label"] for p in f["presets"] if p["active"]] == ["Last 3 Months"]

    def test_resolve_start_only_matching_preset_start_marks_no_preset_active(self):
        f = resolve_date_filter("2026-11-01", None, today=PINNED_TODAY)
        assert not any(p["active"] for p in f["presets"])

    def test_resolve_marks_matching_preset_active(self):
        f = resolve_date_filter("2026-11-01", "2026-11-30", today=PINNED_TODAY)
        active = [p["label"] for p in f["presets"] if p["active"]]
        assert active == ["This Month"]
        none = resolve_date_filter(None, None, today=PINNED_TODAY)
        assert not any(p["active"] for p in none["presets"])

    def test_resolve_presets_present_even_when_filter_invalid(self):
        f = resolve_date_filter("banana", "banana", today=PINNED_TODAY)
        assert len(f["presets"]) == 3


# --------------------------------------------------------------------------
# Filtered query helpers
# --------------------------------------------------------------------------


@pytest.fixture
def dated_user(user_id):
    """User with expenses on known dates, including boundary candidates."""
    _insert_expenses(
        user_id,
        [
            (10.00, "Food", "2025-01-09", "before"),
            (20.00, "Food", "2025-01-10", "on start"),
            (30.00, "Bills", "2025-01-15", "middle"),
            (40.00, "Bills", "2025-01-20", "on end"),
            (50.00, "Health", "2025-01-21", "after"),
        ],
    )
    return user_id


class TestFilteredQueries:
    def test_stats_no_filter_covers_all_rows(self, dated_user):
        stats = get_summary_stats(dated_user)
        assert stats["transaction_count"] == 5
        assert stats["total_spent"] == pytest.approx(150.00)

    def test_stats_range_includes_both_boundary_dates(self, dated_user):
        stats = get_summary_stats(dated_user, start="2025-01-10", end="2025-01-20")
        assert stats["transaction_count"] == 3
        assert stats["total_spent"] == pytest.approx(90.00)
        assert stats["top_category"] == "Bills"

    def test_stats_start_only_includes_start_day_and_later(self, dated_user):
        stats = get_summary_stats(dated_user, start="2025-01-20")
        assert stats["transaction_count"] == 2
        assert stats["total_spent"] == pytest.approx(90.00)

    def test_stats_end_only_includes_end_day_and_earlier(self, dated_user):
        stats = get_summary_stats(dated_user, end="2025-01-10")
        assert stats["transaction_count"] == 2
        assert stats["total_spent"] == pytest.approx(30.00)

    def test_stats_single_day_range_returns_only_that_day(self, dated_user):
        stats = get_summary_stats(dated_user, start="2025-01-15", end="2025-01-15")
        assert stats["transaction_count"] == 1
        assert stats["total_spent"] == pytest.approx(30.00)
        assert stats["top_category"] == "Bills"

    def test_stats_empty_range_returns_zero_and_dash(self, dated_user):
        stats = get_summary_stats(dated_user, start="2030-01-01", end="2030-12-31")
        assert stats["total_spent"] == 0
        assert stats["transaction_count"] == 0
        assert stats["top_category"] == EMPTY

    def test_transactions_filtered_inclusive_and_newest_first(self, dated_user):
        rows = get_recent_transactions(dated_user, start="2025-01-10", end="2025-01-20")
        assert [r["date"] for r in rows] == ["2025-01-20", "2025-01-15", "2025-01-10"]

    def test_transactions_empty_range_returns_empty_list(self, dated_user):
        rows = get_recent_transactions(dated_user, start="2030-01-01", end="2030-01-31")
        assert rows == []

    def test_transactions_filter_capped_at_ten_most_recent(self, user_id):
        _insert_expenses(
            user_id,
            [(1.00 + i, "Food", f"2025-03-{i:02d}", f"row {i}") for i in range(1, 16)],
        )
        rows = get_recent_transactions(user_id, start="2025-03-01", end="2025-03-31")
        assert len(rows) == 10
        assert rows[0]["date"] == "2025-03-15"
        assert rows[-1]["date"] == "2025-03-06"

    def test_stats_count_not_capped_at_ten_when_filtered(self, user_id):
        _insert_expenses(
            user_id,
            [(1.00, "Food", f"2025-03-{i:02d}", None) for i in range(1, 16)],
        )
        stats = get_summary_stats(user_id, start="2025-03-01", end="2025-03-31")
        assert stats["transaction_count"] == 15

    def test_breakdown_filtered_only_includes_range_categories(self, dated_user):
        result = get_category_breakdown(dated_user, start="2025-01-10", end="2025-01-20")
        totals = {r["category"]: r["total"] for r in result}
        assert totals == {"Bills": pytest.approx(70.00), "Food": pytest.approx(20.00)}
        assert "Health" not in totals

    def test_breakdown_empty_range_returns_empty_list(self, dated_user):
        assert get_category_breakdown(dated_user, start="2030-01-01", end="2030-01-31") == []

    def test_breakdown_percentages_sum_to_100_for_even_thirds(self, user_id):
        _insert_expenses(
            user_id,
            [
                (10.00, "Food", "2025-05-05", None),
                (10.00, "Bills", "2025-05-06", None),
                (10.00, "Health", "2025-05-07", None),
            ],
        )
        result = get_category_breakdown(user_id, start="2025-05-01", end="2025-05-31")
        assert len(result) == 3
        assert sum(r["percent"] for r in result) == 100

    @pytest.mark.parametrize(
        "amounts",
        [(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0), (33.33, 33.33, 33.34), (0.01, 99.99, 5.55, 1.11)],
    )
    def test_breakdown_percentages_sum_to_100_parametrized(self, user_id, amounts):
        categories = ["Food", "Bills", "Health", "Shopping", "Other", "Transport", "Entertainment"]
        _insert_expenses(
            user_id,
            [(a, categories[i], "2025-06-10", None) for i, a in enumerate(amounts)],
        )
        result = get_category_breakdown(user_id, start="2025-06-01", end="2025-06-30")
        assert sum(r["percent"] for r in result) == 100

    def test_filtered_views_are_consistent_with_each_other(self, dated_user):
        kwargs = {"start": "2025-01-10", "end": "2025-01-20"}
        stats = get_summary_stats(dated_user, **kwargs)
        rows = get_recent_transactions(dated_user, **kwargs)
        breakdown = get_category_breakdown(dated_user, **kwargs)
        assert stats["transaction_count"] == len(rows)
        assert stats["total_spent"] == pytest.approx(sum(r["amount"] for r in rows))
        assert stats["total_spent"] == pytest.approx(sum(b["total"] for b in breakdown))

    def test_other_users_rows_never_included_in_filtered_results(
        self, dated_user, other_user_id
    ):
        _insert_expenses(
            other_user_id,
            [(999.00, "Secret", "2025-01-15", "other user's expense")],
        )
        kwargs = {"start": "2025-01-01", "end": "2025-01-31"}
        stats = get_summary_stats(dated_user, **kwargs)
        rows = get_recent_transactions(dated_user, **kwargs)
        breakdown = get_category_breakdown(dated_user, **kwargs)
        assert stats["transaction_count"] == 5
        assert stats["total_spent"] == pytest.approx(150.00)
        assert all(r["category"] != "Secret" for r in rows)
        assert all(b["category"] != "Secret" for b in breakdown)

    def test_other_user_with_no_rows_in_range_sees_empty_results(
        self, dated_user, other_user_id
    ):
        kwargs = {"start": "2025-01-01", "end": "2025-01-31"}
        assert get_summary_stats(other_user_id, **kwargs)["transaction_count"] == 0
        assert get_recent_transactions(other_user_id, **kwargs) == []
        assert get_category_breakdown(other_user_id, **kwargs) == []

    def test_date_value_with_sql_metacharacters_is_treated_as_data(self, dated_user):
        bad = "2025-01-01' OR '1'='1"
        stats = get_summary_stats(dated_user, start=bad)
        # Bound as a plain string, so it is just a lower bound compared as text.
        all_rows = get_recent_transactions(dated_user, limit=100)
        assert stats["transaction_count"] == sum(r["date"] >= bad for r in all_rows)

    def test_existing_tables_intact_after_injection_style_value(self, dated_user):
        get_recent_transactions(dated_user, start="'; DROP TABLE expenses; --")
        assert get_summary_stats(dated_user)["transaction_count"] == 5


# --------------------------------------------------------------------------
# GET /profile route
# --------------------------------------------------------------------------


class TestProfileRouteAuth:
    def test_unauthenticated_with_filter_params_redirects_to_login(self, client):
        response = client.get(
            _profile_path(client), params={"start": "2026-01-01", "end": "2026-12-31"}
        )
        assert response.status_code == 303
        location = response.headers["location"]
        assert location.endswith(_login_path(client))
        assert "start" not in location and "end=" not in location

    def test_unauthenticated_without_params_redirects_to_login(self, client):
        response = client.get(_profile_path(client))
        assert response.status_code == 303
        assert response.headers["location"].endswith(_login_path(client))


class TestProfileRouteUnfiltered:
    def test_no_params_shows_all_eight_seed_transactions(self, auth_client):
        response = _get_profile(auth_client)
        assert response.status_code == 200
        assert _row_count(response.text) == 8

    def test_no_params_shows_seed_totals(self, auth_client):
        html = _get_profile(auth_client).text
        assert "₹387.50" in html, "Seed total should be 387.50"

    def test_no_params_uses_recent_transactions_heading_and_no_error(self, auth_client):
        html = _get_profile(auth_client).text
        assert "Recent transactions" in html
        assert "filter-error" not in html

    def test_blank_params_behave_like_no_filter(self, auth_client):
        response = _get_profile(auth_client, start="", end="")
        assert response.status_code == 200
        assert _row_count(response.text) == 8
        assert "filter-error" not in response.text

    def test_page_shows_all_four_pills_and_to_separator(self, auth_client):
        html = _get_profile(auth_client).text
        for label in ("All Time", "This Month", "Last 3 Months", "Last 6 Months"):
            assert re.search(rf">\s*{label}\s*</a>", html), f"Missing pill {label}"
        assert re.search(r">\s*to\s*<", html), "Expected 'to' between date inputs"

    def test_date_inputs_have_aria_labels(self, auth_client):
        html = _get_profile(auth_client).text
        for name in ("start", "end"):
            tag = re.search(rf'<input[^>]*name="{name}"[^>]*>', html)
            assert tag, f"Missing {name} input"
            assert "aria-label=" in tag.group(0), f"{name} input needs aria-label"

    def test_page_contains_filter_form_with_date_inputs(self, auth_client):
        html = _get_profile(auth_client).text
        assert re.search(r'<form[^>]*method="get"', html, re.IGNORECASE)
        assert 'type="date"' in html
        assert 'name="start"' in html
        assert 'name="end"' in html
        assert "Apply" in html
        assert "All Time" in html


class TestProfileRouteFiltered:
    def test_range_shows_only_expenses_in_range(self, auth_client):
        response = _get_profile(auth_client, start=_month_day(10), end=_month_day(20))
        assert response.status_code == 200
        html = response.text
        assert _row_count(html) == 3
        for day in (12, 16, 20):
            assert _month_day(day) in html
        for day in (1, 3, 6, 9, 25):
            assert f'datetime="{_month_day(day)}"' not in html

    def test_range_updates_stats_to_filtered_set(self, auth_client):
        html = _get_profile(auth_client, start=_month_day(10), end=_month_day(20)).text
        assert "₹120.00" in html  # 25 + 80 + 15
        assert "Shopping" in html  # top category in range
        assert "₹387.50" not in html

    def test_range_updates_category_breakdown(self, auth_client):
        html = _get_profile(auth_client, start=_month_day(10), end=_month_day(20)).text
        breakdown = html[html.index("breakdown-list"):]
        assert "Shopping" in breakdown
        assert "Entertainment" in breakdown
        assert "Bills" not in breakdown
        assert "Food" not in breakdown

    def test_expense_on_start_date_is_included(self, auth_client):
        html = _get_profile(auth_client, start=_month_day(12), end=_month_day(20)).text
        assert f'datetime="{_month_day(12)}"' in html
        assert _row_count(html) == 3

    def test_expense_on_end_date_is_included(self, auth_client):
        html = _get_profile(auth_client, start=_month_day(12), end=_month_day(20)).text
        assert f'datetime="{_month_day(20)}"' in html

    def test_day_before_start_and_after_end_are_excluded(self, auth_client):
        html = _get_profile(auth_client, start=_month_day(13), end=_month_day(19)).text
        assert _row_count(html) == 1
        assert f'datetime="{_month_day(16)}"' in html

    def test_start_only_shows_on_or_after(self, auth_client):
        html = _get_profile(auth_client, start=_month_day(20)).text
        assert _row_count(html) == 2
        assert "₹75.00" in html  # 15 + 60

    def test_end_only_shows_on_or_before(self, auth_client):
        html = _get_profile(auth_client, end=_month_day(3)).text
        assert _row_count(html) == 2
        assert "₹57.50" in html  # 12.50 + 45

    def test_active_filter_renames_heading_to_transactions(self, auth_client):
        html = _get_profile(auth_client, start=_month_day(1), end=_month_day(25)).text
        assert "Recent transactions" not in html
        assert ">Transactions</h2>" in html

    def test_inputs_are_prefilled_with_active_range(self, auth_client):
        html = _get_profile(auth_client, start=_month_day(10), end=_month_day(20)).text
        assert f'value="{_month_day(10)}"' in html
        assert f'value="{_month_day(20)}"' in html

    def test_non_padded_date_is_normalised_in_inputs(self, auth_client):
        html = _get_profile(auth_client, start="2020-1-5", end="2020-1-9").text
        assert 'value="2020-01-05"' in html
        assert 'value="2020-01-09"' in html

    def test_old_expenses_are_excluded_from_current_month_and_found_in_their_range(
        self, auth_client, demo_id
    ):
        _insert_expenses(demo_id, [(7.77, "Other", "2020-06-15", "ancient purchase")])
        in_range = _get_profile(auth_client, start="2020-06-01", end="2020-06-30").text
        assert "ancient purchase" in in_range
        assert _row_count(in_range) == 1
        unfiltered = _get_profile(auth_client).text
        assert "ancient purchase" in unfiltered  # still within the 10 most recent


class TestProfileRouteEmptyRange:
    def test_empty_range_shows_zero_stats_and_empty_states(self, auth_client):
        response = _get_profile(auth_client, start="2000-01-01", end="2000-01-31")
        assert response.status_code == 200
        html = response.text
        assert "₹0.00" in html
        assert EMPTY in html
        assert "No transactions in this range." in html
        assert "No spending in this range." in html
        assert _row_count(html) == 0
        assert "filter-error" not in html

    def test_unfiltered_empty_user_uses_default_empty_states(self, client, demo_id):
        with closing(db.get_db()) as conn, conn:
            conn.execute("DELETE FROM expenses WHERE user_id = ?", (demo_id,))
        client.post(
            client.app.url_path_for("login"),
            content=f"email={DEMO_EMAIL}&password={DEMO_PASSWORD}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        html = _get_profile(client).text
        assert "No transactions yet." in html
        assert "No spending yet." in html


class TestProfileRouteInvalidInput:
    @pytest.mark.parametrize(
        "bad", ["banana", "2026-02-30", "2026-13-45", "<script>alert(1)</script>"]
    )
    def test_invalid_start_returns_200_with_inline_error(self, auth_client, bad):
        response = _get_profile(auth_client, start=bad)
        assert response.status_code == 200
        assert "filter-error" in response.text
        assert _row_count(response.text) == 8, "Invalid bound must leave data unfiltered"

    def test_invalid_end_returns_200_with_inline_error(self, auth_client):
        response = _get_profile(auth_client, end="banana")
        assert response.status_code == 200
        assert "filter-error" in response.text
        assert _row_count(response.text) == 8

    def test_raw_script_value_is_not_reflected_unescaped(self, auth_client):
        html = _get_profile(auth_client, start="<script>alert(1)</script>").text
        assert "<script>alert(1)</script>" not in html

    def test_sql_injection_style_value_does_not_crash_or_leak(self, auth_client):
        response = _get_profile(auth_client, start="' OR 1=1; DROP TABLE expenses; --")
        assert response.status_code == 200
        assert _row_count(response.text) == 8
        # Table must still exist afterwards.
        assert _row_count(_get_profile(auth_client).text) == 8

    def test_valid_start_with_invalid_end_still_applies_start(self, auth_client):
        response = _get_profile(auth_client, start=_month_day(20), end="banana")
        assert response.status_code == 200
        assert "filter-error" in response.text
        assert _row_count(response.text) == 2

    def test_invalid_start_with_valid_end_still_applies_end(self, auth_client):
        response = _get_profile(auth_client, start="banana", end=_month_day(3))
        assert response.status_code == 200
        assert "filter-error" in response.text
        assert _row_count(response.text) == 2

    def test_start_after_end_shows_error_and_unfiltered_data(self, auth_client):
        response = _get_profile(auth_client, start=_month_day(20), end=_month_day(3))
        assert response.status_code == 200
        assert "filter-error" in response.text
        assert _row_count(response.text) == 8

    def test_start_after_end_keeps_entered_values_in_inputs(self, auth_client):
        html = _get_profile(auth_client, start=_month_day(20), end=_month_day(3)).text
        assert f'value="{_month_day(20)}"' in html
        assert f'value="{_month_day(3)}"' in html

    def test_very_long_value_does_not_crash(self, auth_client):
        response = _get_profile(auth_client, start="9" * 5000)
        assert response.status_code == 200
        assert "filter-error" in response.text


class TestProfileRouteLinks:
    def test_all_time_link_points_to_profile_without_params(self, auth_client):
        html = _get_profile(auth_client, start=_month_day(1), end=_month_day(5)).text
        profile = _profile_path(auth_client)
        match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>\s*All Time\s*</a>', html)
        assert match, "Expected an All Time link"
        href = match.group(1)
        # url_for() in templates renders an absolute URL, so compare the path.
        assert href.endswith(profile)
        assert "?" not in href

    def test_form_action_targets_profile(self, auth_client):
        html = _get_profile(auth_client).text
        profile = _profile_path(auth_client)
        assert re.search(rf'<form[^>]*action="[^"]*{re.escape(profile)}"', html)

    def test_preset_links_apply_expected_ranges(self, auth_client):
        html = _get_profile(auth_client).text
        presets = resolve_date_filter(None, None)["presets"]
        profile = _profile_path(auth_client)
        assert [p["label"] for p in presets] == ["This Month", "Last 3 Months", "Last 6 Months"]
        for p in presets:
            href = f'{profile}?start={p["start"]}&amp;end={p["end"]}'
            assert href in html, f"Missing preset link for {p['label']}"
            assert p["label"] in html

    def test_this_month_preset_includes_all_seed_expenses(self, auth_client):
        preset = next(
            p for p in resolve_date_filter(None, None)["presets"]
            if p["label"] == "This Month"
        )
        response = _get_profile(auth_client, start=preset["start"], end=preset["end"])
        assert response.status_code == 200
        assert _row_count(response.text) == 8

    def test_last_6_months_preset_ends_today(self, auth_client):
        preset = next(
            p for p in resolve_date_filter(None, None)["presets"]
            if p["label"] == "Last 6 Months"
        )
        response = _get_profile(auth_client, start=preset["start"], end=preset["end"])
        seed_days = (1, 3, 6, 9, 12, 16, 20, 25)
        expected = sum(day <= date.today().day for day in seed_days)
        assert _row_count(response.text) == expected


def _pill_classes(html, label):
    match = re.search(
        rf'<a[^>]*class="([^"]*)"[^>]*>\s*{re.escape(label)}\s*</a>', html
    )
    assert match, f"Expected a pill link for {label}"
    return match.group(1)


class TestProfileRoutePillHighlight:
    def test_all_time_pill_highlighted_when_no_filter(self, auth_client):
        html = _get_profile(auth_client).text
        assert "active" in _pill_classes(html, "All Time")
        for label in ("This Month", "Last 3 Months", "Last 6 Months"):
            assert "active" not in _pill_classes(html, label)

    @pytest.mark.parametrize(
        "label", ["This Month", "Last 3 Months", "Last 6 Months"]
    )
    def test_preset_pill_highlighted_when_its_range_is_active(
        self, auth_client, label
    ):
        preset = next(
            p for p in resolve_date_filter(None, None)["presets"]
            if p["label"] == label
        )
        html = _get_profile(auth_client, start=preset["start"], end=preset["end"]).text
        assert "active" in _pill_classes(html, label)
        assert "active" not in _pill_classes(html, "All Time")

    def test_custom_range_highlights_no_pill(self, auth_client):
        html = _get_profile(auth_client, start="2000-01-01", end="2000-01-02").text
        for label in ("All Time", "This Month", "Last 3 Months", "Last 6 Months"):
            assert "active" not in _pill_classes(html, label)


class TestProfileRouteCapAndPercent:
    def test_filtered_list_is_capped_at_ten_but_count_is_not(
        self, auth_client, demo_id
    ):
        _insert_expenses(
            demo_id,
            [(2.00, "Food", f"2019-03-{i:02d}", f"cap {i}") for i in range(1, 16)],
        )
        html = _get_profile(auth_client, start="2019-03-01", end="2019-03-31").text
        assert _row_count(html) == 10
        assert 'datetime="2019-03-15"' in html
        assert 'datetime="2019-03-05"' not in html, "Oldest rows beyond 10 dropped"
        assert "₹30.00" in html, "Total must cover all 15 rows"

    @pytest.mark.parametrize(
        "params",
        [
            {},
            {"start": "2019-03-01", "end": "2019-03-31"},
            {"start": "2019-03-10"},
            {"end": "2019-03-10"},
        ],
    )
    def test_breakdown_percentages_in_page_sum_to_100(
        self, auth_client, demo_id, params
    ):
        _insert_expenses(
            demo_id,
            [
                (10.00, "Food", "2019-03-05", None),
                (10.00, "Bills", "2019-03-10", None),
                (10.00, "Health", "2019-03-15", None),
            ],
        )
        html = _get_profile(auth_client, **params).text
        pcts = [int(p) for p in re.findall(r'class="breakdown-pct">(\d+)%', html)]
        assert pcts, "Expected breakdown rows"
        assert sum(pcts) == 100

    def test_empty_range_stats_show_zero_count_and_dash(self, auth_client):
        html = _get_profile(auth_client, start="2000-01-01", end="2000-01-31").text
        assert re.search(r"Transactions</span>\s*<span[^>]*>0</span>", html)
        assert re.search(r"Top category</span>\s*<span[^>]*>—</span>", html)

    def test_injection_style_end_value_does_not_crash(self, auth_client):
        response = _get_profile(auth_client, end="2026-01-01' OR '1'='1")
        assert response.status_code == 200
        assert "filter-error" in response.text
        assert _row_count(response.text) == 8


@pytest.fixture
def other_user_id_after_client(client):
    """Second user created after the app has initialised the DB."""
    return db.create_user("Other Person", "other-person@example.com", "secret123")


class TestProfileRouteIsolation:
    def test_other_users_expenses_never_appear_in_filtered_view(
        self, auth_client, other_user_id_after_client
    ):
        _insert_expenses(
            other_user_id_after_client,
            [(555.55, "Secret", _month_day(12), "OtherUserSecretItem")],
        )
        html = _get_profile(
            auth_client, start=_month_day(1), end=_month_day(28)
        ).text
        assert "OtherUserSecretItem" not in html
        assert "Secret" not in html
        assert "₹555.55" not in html
        assert _row_count(html) == 8
