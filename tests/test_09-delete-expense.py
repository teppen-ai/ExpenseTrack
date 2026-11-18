"""Tests for feature 09-delete-expense: POST /expenses/{id}/delete."""

import re
from contextlib import closing
from urllib.parse import urlencode

import pytest

from database import db

DEMO_EMAIL = "demo@expensetrack.com"
DEMO_PASSWORD = "demo123"
OTHER_EMAIL = "other@example.com"
OTHER_PASSWORD = "secret123"
FORM_HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}
MARKER = "DeleteMarkerQwz"
KEEP_MARKER = "KeepMarkerQwz"
# Far-future date so inserted rows always rank in the profile's 10 most recent.
RECENT_DATE = "2099-01-01"
BIG_AMOUNT = 98765.43


# --------------------------------------------------------------------------
# Helpers and fixtures
# --------------------------------------------------------------------------


def _login(client, email, password):
    client.cookies.clear()
    response = client.post(
        client.app.url_path_for("login"),
        content=urlencode({"email": email, "password": password}),
        headers=FORM_HEADERS,
    )
    assert response.status_code == 303, "Login should redirect with 303"


@pytest.fixture
def auth_client(client):
    _login(client, DEMO_EMAIL, DEMO_PASSWORD)
    return client


@pytest.fixture
def demo_id(client):
    return db.get_user_by_email(DEMO_EMAIL)["id"]


@pytest.fixture
def other_id(client):
    return db.create_user("Other", OTHER_EMAIL, OTHER_PASSWORD)


def _insert(user_id, **overrides):
    data = {
        "amount": 42.0,
        "category": "Transport",
        "date": RECENT_DATE,
        "description": MARKER,
    }
    data.update(overrides)
    with closing(db.get_db()) as conn:
        cur = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                data["amount"],
                data["category"],
                data["date"],
                data["description"],
            ),
        )
        conn.commit()
        return cur.lastrowid


@pytest.fixture
def expense_id(demo_id):
    return _insert(demo_id)


@pytest.fixture
def other_expense_id(other_id):
    return _insert(other_id)


def _all_rows():
    with closing(db.get_db()) as conn:
        rows = conn.execute("SELECT * FROM expenses ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def _row(expense_id):
    return next((r for r in _all_rows() if r["id"] == expense_id), None)


def _delete_path(client, expense_id):
    return client.app.url_path_for("delete_expense", id=expense_id)


def _profile_path(client):
    return client.app.url_path_for("profile")


def _login_path(client):
    return client.app.url_path_for("login")


def _delete(client, expense_id):
    return client.post(_delete_path(client, expense_id))


def _forms_for(html, path):
    """Return the <form ...>...</form> blocks whose action ends with path."""
    forms = re.findall(r"<form\b.*?</form>", html, flags=re.DOTALL | re.IGNORECASE)
    pattern = rf'action="[^"]*{re.escape(path)}"'
    return [f for f in forms if re.search(pattern, f)]


def _opening_tag(form):
    return re.match(r"<form\b[^>]*>", form, flags=re.IGNORECASE).group(0)


# --------------------------------------------------------------------------
# Auth guard
# --------------------------------------------------------------------------


class TestAuthGuard:
    def test_post_logged_out_redirects_to_login_and_deletes_nothing(
        self, client, expense_id
    ):
        before = _all_rows()
        response = _delete(client, expense_id)
        assert response.status_code == 303
        assert response.headers["location"] == _login_path(client)
        assert _all_rows() == before, "Nothing may be deleted when logged out"

    def test_post_after_logout_redirects_to_login_and_deletes_nothing(
        self, auth_client, expense_id
    ):
        auth_client.get(auth_client.app.url_path_for("logout"))
        response = _delete(auth_client, expense_id)
        assert response.status_code == 303
        assert response.headers["location"] == _login_path(auth_client)
        assert _row(expense_id) is not None


# --------------------------------------------------------------------------
# Successful delete
# --------------------------------------------------------------------------


class TestDeleteSuccess:
    def test_post_redirects_303_to_profile(self, auth_client, expense_id):
        response = _delete(auth_client, expense_id)
        assert response.status_code == 303
        assert response.headers["location"] == _profile_path(auth_client)

    def test_post_removes_only_target_row(self, auth_client, demo_id, expense_id):
        keep_id = _insert(demo_id, description=KEEP_MARKER, amount=7.5)
        before = _all_rows()
        _delete(auth_client, expense_id)
        after = _all_rows()
        assert len(after) == len(before) - 1, "Row count must drop by exactly one"
        assert _row(expense_id) is None, "Target expense should be deleted"
        assert after == [r for r in before if r["id"] != expense_id]
        assert _row(keep_id) is not None

    def test_post_does_not_touch_other_users_expenses(
        self, auth_client, expense_id, other_expense_id
    ):
        before = _row(other_expense_id)
        _delete(auth_client, expense_id)
        assert _row(other_expense_id) == before

    def test_post_ignores_form_fields(self, auth_client, expense_id, other_id):
        response = auth_client.post(
            _delete_path(auth_client, expense_id),
            content=urlencode({"user_id": str(other_id), "amount": "1"}),
            headers=FORM_HEADERS,
        )
        assert response.status_code == 303
        assert _row(expense_id) is None

    def test_post_repeat_returns_404(self, auth_client, expense_id):
        assert _delete(auth_client, expense_id).status_code == 303
        assert _delete(auth_client, expense_id).status_code == 404

    def test_post_expense_gone_from_profile_list(
        self, auth_client, demo_id, expense_id
    ):
        _insert(demo_id, description=KEEP_MARKER)
        before = auth_client.get(_profile_path(auth_client)).text
        assert MARKER in before, "Precondition: expense listed before delete"
        _delete(auth_client, expense_id)
        after = auth_client.get(_profile_path(auth_client)).text
        assert MARKER not in after, "Deleted expense should leave the list"
        assert KEEP_MARKER in after, "Other expenses should remain"

    def test_post_totals_and_breakdown_updated(self, client, other_id):
        """A fresh user's only expense: after deleting, totals/breakdown clear."""
        _login(client, OTHER_EMAIL, OTHER_PASSWORD)
        eid = _insert(other_id, amount=BIG_AMOUNT, category="Shopping")
        before = client.get(_profile_path(client)).text
        formatted = ("98,765.43", "98765.43")
        assert any(f in before for f in formatted), "Total expected before delete"
        assert "Shopping" in before, "Category expected in breakdown before delete"
        _delete(client, eid)
        after = client.get(_profile_path(client)).text
        assert not any(f in after for f in formatted), "Total should be removed"
        assert "Shopping" not in after, "Category should leave the breakdown"


# --------------------------------------------------------------------------
# Not found / ownership / validation
# --------------------------------------------------------------------------


class TestNotFoundAndOwnership:
    def test_post_nonexistent_id_returns_404_and_deletes_nothing(self, auth_client):
        before = _all_rows()
        response = _delete(auth_client, 999999)
        assert response.status_code == 404
        assert _all_rows() == before

    def test_post_other_users_expense_returns_404_and_row_remains(
        self, auth_client, other_expense_id
    ):
        before = _row(other_expense_id)
        response = _delete(auth_client, other_expense_id)
        assert response.status_code == 404
        assert _row(other_expense_id) == before

    def test_other_user_and_missing_are_indistinguishable(
        self, auth_client, other_expense_id
    ):
        missing = _delete(auth_client, 999999)
        foreign = _delete(auth_client, other_expense_id)
        assert missing.status_code == foreign.status_code == 404
        assert missing.text == foreign.text, "404 bodies must not leak existence"

    def test_post_other_user_cannot_delete_demos_expense(
        self, client, other_id, expense_id
    ):
        _login(client, OTHER_EMAIL, OTHER_PASSWORD)
        response = _delete(client, expense_id)
        assert response.status_code == 404
        assert _row(expense_id) is not None

    @pytest.mark.parametrize("bad_id", ["abc", "1.5", "1%20OR%201=1"])
    def test_post_non_integer_id_returns_422_and_deletes_nothing(
        self, auth_client, expense_id, bad_id
    ):
        before = _all_rows()
        response = auth_client.post(f"/expenses/{bad_id}/delete")
        assert response.status_code == 422
        assert _all_rows() == before


# --------------------------------------------------------------------------
# Method restrictions
# --------------------------------------------------------------------------


class TestMethodNotAllowed:
    @pytest.mark.parametrize("method", ["get", "put", "patch", "delete"])
    def test_non_post_logged_in_returns_405_and_deletes_nothing(
        self, auth_client, expense_id, method
    ):
        response = getattr(auth_client, method)(_delete_path(auth_client, expense_id))
        assert response.status_code == 405
        assert _row(expense_id) is not None

    def test_get_logged_out_returns_405(self, client, expense_id):
        response = client.get(_delete_path(client, expense_id))
        assert response.status_code == 405
        assert _row(expense_id) is not None


# --------------------------------------------------------------------------
# Profile page delete forms
# --------------------------------------------------------------------------


class TestProfileDeleteForms:
    def test_profile_delete_form_markup(self, auth_client, expense_id):
        html = auth_client.get(_profile_path(auth_client)).text
        forms = _forms_for(html, _delete_path(auth_client, expense_id))
        assert len(forms) == 1, "Exactly one delete form expected for the row"
        form = forms[0]
        opening = _opening_tag(form)
        assert re.search(r'method="post"', opening, flags=re.IGNORECASE)
        confirm = re.search(r'data-confirm="([^"]+)"', opening)
        assert confirm and confirm.group(1).strip(), "Non-empty data-confirm needed"
        assert re.search(r"<button\b", form, flags=re.IGNORECASE)
        assert "Delete" in form

    def test_profile_delete_form_in_same_row_as_edit_link(
        self, auth_client, expense_id
    ):
        html = auth_client.get(_profile_path(auth_client)).text
        edit_path = auth_client.app.url_path_for("edit_expense", id=expense_id)
        delete_path = _delete_path(auth_client, expense_id)
        rows = re.findall(r"<tr\b.*?</tr>", html, flags=re.DOTALL | re.IGNORECASE)
        matching = [r for r in rows if edit_path in r]
        assert len(matching) == 1, "Exactly one row with the edit link expected"
        assert delete_path in matching[0], "Delete form must sit next to Edit"

    def test_profile_has_form_for_every_listed_row(self, auth_client, demo_id):
        ids = [_insert(demo_id, description=f"Row{i}") for i in range(3)]
        html = auth_client.get(_profile_path(auth_client)).text
        for eid in ids:
            assert _forms_for(
                html, _delete_path(auth_client, eid)
            ), f"Delete form missing for expense {eid}"

    def test_profile_omits_other_users_delete_form_and_get_links(
        self, auth_client, expense_id, other_expense_id
    ):
        html = auth_client.get(_profile_path(auth_client)).text
        assert not _forms_for(html, _delete_path(auth_client, other_expense_id))
        own = _delete_path(auth_client, expense_id)
        assert f'href="{own}"' not in html, "Delete must never be a GET link"

    def test_profile_form_removed_after_delete(self, auth_client, expense_id):
        path = _delete_path(auth_client, expense_id)
        _delete(auth_client, expense_id)
        html = auth_client.get(_profile_path(auth_client)).text
        assert not _forms_for(html, path), "Deleted row must lose its form"

    def test_profile_empty_state_has_no_delete_form(self, client, other_id):
        _login(client, OTHER_EMAIL, OTHER_PASSWORD)
        html = client.get(_profile_path(client)).text
        assert "/delete" not in html
