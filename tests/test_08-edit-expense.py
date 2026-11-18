"""Tests for feature 08-edit-expense: GET/POST /expenses/{id}/edit."""

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
ORIGINAL = {
    "amount": 42.0,
    "category": "Transport",
    "date": "2026-02-10",
    "description": "Original desc",
}
CREATED_AT = "2020-01-01 00:00:00"


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
    data = dict(ORIGINAL)
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
        conn.execute(
            "UPDATE expenses SET created_at = ? WHERE id = ?",
            (CREATED_AT, cur.lastrowid),
        )
        conn.commit()
        return cur.lastrowid


@pytest.fixture
def expense_id(client, demo_id):
    return _insert(demo_id)


@pytest.fixture
def other_expense_id(other_id):
    return _insert(other_id)


def _row(expense_id):
    with closing(db.get_db()) as conn:
        row = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        return dict(row) if row else None


def _count():
    with closing(db.get_db()) as conn:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]


def _edit_path(client, expense_id):
    return client.app.url_path_for("edit_expense", id=expense_id)


def _profile_path(client):
    return client.app.url_path_for("profile")


def _login_path(client):
    return client.app.url_path_for("login")


def _valid(**overrides):
    data = {
        "amount": "12.50",
        "category": "Food",
        "date": "2026-03-15",
        "description": "Lunch",
    }
    data.update(overrides)
    return data


def _post(client, expense_id, **fields):
    return client.post(
        _edit_path(client, expense_id),
        content=urlencode(fields),
        headers=FORM_HEADERS,
    )


def _assert_unchanged(expense_id):
    row = _row(expense_id)
    assert row["amount"] == pytest.approx(ORIGINAL["amount"])
    assert row["category"] == ORIGINAL["category"]
    assert row["date"] == ORIGINAL["date"]
    assert row["description"] == ORIGINAL["description"]
    assert row["created_at"] == CREATED_AT


# --------------------------------------------------------------------------
# Auth guard
# --------------------------------------------------------------------------


class TestAuthGuard:
    def test_get_edit_logged_out_redirects_to_login(self, client, expense_id):
        response = client.get(_edit_path(client, expense_id))
        assert response.status_code == 303
        assert response.headers["location"] == _login_path(client)

    def test_post_edit_logged_out_redirects_and_row_unchanged(self, client, expense_id):
        before = _count()
        response = _post(client, expense_id, **_valid())
        assert response.status_code == 303
        assert response.headers["location"] == _login_path(client)
        assert _count() == before
        _assert_unchanged(expense_id)


# --------------------------------------------------------------------------
# GET form
# --------------------------------------------------------------------------


class TestEditForm:
    def test_get_returns_200_with_edit_title(self, auth_client, expense_id):
        response = auth_client.get(_edit_path(auth_client, expense_id))
        assert response.status_code == 200
        assert "Edit expense" in response.text

    def test_get_prefills_values(self, auth_client, expense_id):
        html = auth_client.get(_edit_path(auth_client, expense_id)).text
        assert 'value="42' in html, "Amount should be pre-filled"
        assert "2026-02-10" in html, "ISO date should be pre-filled"
        assert "Original desc" in html, "Description should be pre-filled"

    def test_get_selects_stored_category(self, auth_client, expense_id):
        html = auth_client.get(_edit_path(auth_client, expense_id)).text
        stored = re.search(r'<option value="Transport"[^>]*>', html)
        assert stored, "Stored category option expected"
        assert "selected" in stored.group(
            0
        ), "Stored category should be the selected option"
        placeholder = re.search(r'<option value=""[^>]*>', html)
        assert placeholder, "Placeholder option expected"
        assert "selected" not in placeholder.group(
            0
        ), "Placeholder must not be selected when a category is stored"

    def test_get_has_form_action_and_cancel_link(self, auth_client, expense_id):
        html = auth_client.get(_edit_path(auth_client, expense_id)).text
        assert _edit_path(auth_client, expense_id) in html, "Form action expected"
        assert _profile_path(auth_client) in html, "Cancel link to profile expected"
        for name in ("amount", "category", "date", "description"):
            assert f'name="{name}"' in html

    @pytest.mark.parametrize(
        "stored,rendered",
        [(12.5, 'value="12.5"'), (1000000, 'value="1000000')],
    )
    def test_get_amount_rendered_without_float_noise(
        self, auth_client, demo_id, stored, rendered
    ):
        eid = _insert(demo_id, amount=stored)
        html = auth_client.get(_edit_path(auth_client, eid)).text
        assert rendered in html
        assert "12.500000" not in html

    def test_get_script_description_is_escaped(self, auth_client, demo_id):
        payload = "<script>alert(1)</script>"
        eid = _insert(demo_id, description=payload)
        html = auth_client.get(_edit_path(auth_client, eid)).text
        assert payload not in html, "Raw <script> must not appear"
        assert "&lt;script&gt;" in html

    def test_get_null_description_renders_form(self, auth_client, demo_id):
        eid = _insert(demo_id, description=None)
        response = auth_client.get(_edit_path(auth_client, eid))
        assert response.status_code == 200
        assert "None" not in response.text, "NULL must not render as 'None'"


# --------------------------------------------------------------------------
# Successful update
# --------------------------------------------------------------------------


class TestUpdateSuccess:
    def test_post_valid_redirects_to_profile(self, auth_client, expense_id):
        response = _post(auth_client, expense_id, **_valid())
        assert response.status_code == 303
        assert response.headers["location"] == _profile_path(auth_client)

    def test_post_valid_updates_row_without_new_row(
        self, auth_client, expense_id, demo_id
    ):
        before = _count()
        _post(auth_client, expense_id, **_valid())
        assert _count() == before, "Edit must not create or delete rows"
        row = _row(expense_id)
        assert row["amount"] == pytest.approx(12.50)
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-15"
        assert row["description"] == "Lunch"
        assert row["user_id"] == demo_id

    def test_post_valid_preserves_created_at(self, auth_client, expense_id):
        _post(auth_client, expense_id, **_valid())
        assert _row(expense_id)["created_at"] == CREATED_AT

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_post_blank_description_stored_as_null(
        self, auth_client, expense_id, blank
    ):
        response = _post(auth_client, expense_id, **_valid(description=blank))
        assert response.status_code == 303
        assert _row(expense_id)["description"] is None

    def test_post_blank_description_displays_dash_on_profile(self, client, other_id):
        eid = _insert(other_id)
        _login(client, OTHER_EMAIL, OTHER_PASSWORD)
        _post(client, eid, **_valid(description=""))
        html = client.get(_profile_path(client)).text
        assert "—" in html, "NULL description should display as an em dash"

    def test_post_profile_reflects_update(self, auth_client, expense_id):
        _post(auth_client, expense_id, **_valid(description="UpdatedMarkerXyz"))
        html = auth_client.get(_profile_path(auth_client)).text
        assert "UpdatedMarkerXyz" in html
        assert "Original desc" not in html

    @pytest.mark.parametrize("amount", ["0.01", "1000000"])
    def test_post_boundary_amounts_accepted(self, auth_client, expense_id, amount):
        response = _post(auth_client, expense_id, **_valid(amount=amount))
        assert response.status_code == 303
        assert _row(expense_id)["amount"] == pytest.approx(float(amount))

    def test_post_user_id_form_field_is_ignored(
        self, auth_client, expense_id, demo_id, other_id
    ):
        _post(auth_client, expense_id, **_valid(user_id=str(other_id)))
        assert _row(expense_id)["user_id"] == demo_id

    def test_post_sql_injection_in_description_stored_literally(
        self, auth_client, expense_id
    ):
        payload = "x'); DROP TABLE expenses;--"
        response = _post(auth_client, expense_id, **_valid(description=payload))
        assert response.status_code == 303
        assert _row(expense_id)["description"] == payload


# --------------------------------------------------------------------------
# Validation failures
# --------------------------------------------------------------------------


class TestValidationFailures:
    def _assert_rejected(self, client, expense_id, **overrides):
        before = _count()
        response = _post(client, expense_id, **_valid(**overrides))
        assert response.status_code == 400, f"Expected 400 for {overrides}"
        assert _count() == before
        _assert_unchanged(expense_id)
        return response

    @pytest.mark.parametrize(
        "amount", ["", "0", "-5", "abc", "nan", "inf", "1000000.01", "1.234"]
    )
    def test_post_invalid_amount_returns_400(self, auth_client, expense_id, amount):
        self._assert_rejected(auth_client, expense_id, amount=amount)

    @pytest.mark.parametrize("category", ["", "Groceries", "food"])
    def test_post_invalid_category_returns_400(self, auth_client, expense_id, category):
        self._assert_rejected(auth_client, expense_id, category=category)

    @pytest.mark.parametrize("bad_date", ["2026-02-30", "abc", "26-1-1", ""])
    def test_post_invalid_date_returns_400(self, auth_client, expense_id, bad_date):
        self._assert_rejected(auth_client, expense_id, date=bad_date)

    def test_post_description_200_chars_accepted(self, auth_client, expense_id):
        response = _post(auth_client, expense_id, **_valid(description="a" * 200))
        assert response.status_code == 303
        assert _row(expense_id)["description"] == "a" * 200

    def test_post_description_201_chars_rejected(self, auth_client, expense_id):
        self._assert_rejected(auth_client, expense_id, description="a" * 201)

    def test_post_failure_shows_error_and_preserves_values(
        self, auth_client, expense_id
    ):
        response = self._assert_rejected(
            auth_client,
            expense_id,
            amount="abc",
            description="KeepMe",
            category="Bills",
            date="2026-04-01",
        )
        html = response.text
        assert 'name="amount"' in html, "Form should be re-rendered"
        assert "Edit expense" in html, "Should still be the edit form"
        assert "Amount must be a valid number" in html or "amount" in html.lower()
        assert "abc" in html, "Entered amount should be preserved"
        assert "KeepMe" in html, "Entered description should be preserved"
        assert "2026-04-01" in html, "Entered date should be preserved"
        assert (
            _edit_path(auth_client, expense_id) in html
        ), "Form should still post to the edit URL"

    def test_post_failure_shows_error_message_element(self, auth_client, expense_id):
        response = self._assert_rejected(auth_client, expense_id, amount="")
        assert "Please enter an amount" in response.text

    def test_post_failure_script_description_escaped(self, auth_client, expense_id):
        payload = "<script>alert(1)</script>"
        response = self._assert_rejected(
            auth_client, expense_id, amount="abc", description=payload
        )
        assert payload not in response.text
        assert "&lt;script&gt;" in response.text


# --------------------------------------------------------------------------
# Not found / ownership
# --------------------------------------------------------------------------


class TestNotFoundAndOwnership:
    def test_get_nonexistent_id_returns_404(self, auth_client):
        response = auth_client.get(_edit_path(auth_client, 999999))
        assert response.status_code == 404

    def test_post_nonexistent_id_returns_404_and_inserts_nothing(self, auth_client):
        before = _count()
        response = _post(auth_client, 999999, **_valid())
        assert response.status_code == 404
        assert _count() == before

    def test_get_other_users_expense_returns_404(self, auth_client, other_expense_id):
        response = auth_client.get(_edit_path(auth_client, other_expense_id))
        assert response.status_code == 404
        assert "Original desc" not in response.text

    def test_post_other_users_expense_returns_404_and_row_unchanged(
        self, auth_client, other_expense_id, other_id
    ):
        response = _post(auth_client, other_expense_id, **_valid())
        assert response.status_code == 404
        _assert_unchanged(other_expense_id)
        assert _row(other_expense_id)["user_id"] == other_id

    def test_post_other_users_expense_invalid_data_still_404(
        self, auth_client, other_expense_id
    ):
        response = _post(auth_client, other_expense_id, **_valid(amount="abc"))
        assert response.status_code == 404
        _assert_unchanged(other_expense_id)

    def test_post_claiming_other_users_expense_via_user_id_field_fails(
        self, auth_client, other_expense_id, demo_id
    ):
        response = _post(auth_client, other_expense_id, **_valid(user_id=str(demo_id)))
        assert response.status_code == 404
        assert _row(other_expense_id)["user_id"] != demo_id

    @pytest.mark.parametrize("method", ["get", "post"])
    def test_non_integer_id_returns_422(self, auth_client, method):
        path = "/expenses/abc/edit"
        if method == "get":
            response = auth_client.get(path)
        else:
            response = auth_client.post(
                path, content=urlencode(_valid()), headers=FORM_HEADERS
            )
        assert response.status_code == 422


# --------------------------------------------------------------------------
# Add page and delete stub unaffected
# --------------------------------------------------------------------------


class TestAddPageUnchanged:
    def test_add_page_still_shows_add_title_button_and_action(self, auth_client):
        add_path = auth_client.app.url_path_for("add_expense")
        html = auth_client.get(add_path).text
        assert "Add expense" in html
        assert "Edit expense" not in html
        assert add_path in html, "Add form should post to /expenses/add"
        assert (
            "/edit" not in html.split("<main", 1)[-1]
        ), "Add page must not point at an edit URL"


# --------------------------------------------------------------------------
# Profile page Edit links
# --------------------------------------------------------------------------


class TestProfileEditLinks:
    def test_profile_shows_edit_link_for_each_expense(self, auth_client, expense_id):
        html = auth_client.get(_profile_path(auth_client)).text
        path = _edit_path(auth_client, expense_id)
        assert (
            f'href="{path}"' in html or f'{path}"' in html
        ), "Profile should link to the edit path"
        assert "Edit" in html
        assert "Actions" in html, "Actions column header expected"

    def test_profile_links_only_to_own_expenses(
        self, auth_client, expense_id, other_expense_id
    ):
        html = auth_client.get(_profile_path(auth_client)).text
        other_path = _edit_path(auth_client, other_expense_id)
        assert f'{other_path}"' not in html

    def test_profile_empty_state_colspan_is_five(self, client, other_id):
        _login(client, OTHER_EMAIL, OTHER_PASSWORD)
        html = client.get(_profile_path(client)).text
        assert 'colspan="5"' in html, "Empty-state row must span 5 columns"
        assert 'colspan="4"' not in html
