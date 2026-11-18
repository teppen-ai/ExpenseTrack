"""Tests for feature 07-add-expense: GET/POST /expenses/add."""

from contextlib import closing
from datetime import date

import pytest

from database import db

DEMO_EMAIL = "demo@expensetrack.com"
DEMO_PASSWORD = "demo123"
FORM_HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}
ALL_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


# --------------------------------------------------------------------------
# Helpers and fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def auth_client(client):
    response = client.post(
        client.app.url_path_for("login"),
        content=f"email={DEMO_EMAIL}&password={DEMO_PASSWORD}",
        headers=FORM_HEADERS,
    )
    assert response.status_code == 303, "Login should redirect with 303"
    return client


@pytest.fixture
def demo_id(client):
    return db.get_user_by_email(DEMO_EMAIL)["id"]


def _add_path(client):
    return client.app.url_path_for("add_expense")


def _profile_path(client):
    return client.app.url_path_for("profile")


def _login_path(client):
    return client.app.url_path_for("login")


def _post(client, **fields):
    from urllib.parse import urlencode

    return client.post(
        _add_path(client), content=urlencode(fields), headers=FORM_HEADERS
    )


def _valid(**overrides):
    data = {
        "amount": "12.50",
        "category": "Food",
        "date": "2026-03-15",
        "description": "Lunch",
    }
    data.update(overrides)
    return data


def _count():
    with closing(db.get_db()) as conn:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]


def _latest():
    with closing(db.get_db()) as conn:
        return conn.execute(
            "SELECT * FROM expenses ORDER BY id DESC LIMIT 1"
        ).fetchone()


# --------------------------------------------------------------------------
# Auth guard
# --------------------------------------------------------------------------


class TestAuthGuard:
    def test_get_add_expense_logged_out_redirects_to_login(self, client):
        response = client.get(_add_path(client))
        assert response.status_code == 303
        assert response.headers["location"] == _login_path(client)

    def test_post_add_expense_logged_out_redirects_and_inserts_nothing(self, client):
        before = _count()
        response = _post(client, **_valid())
        assert response.status_code == 303
        assert response.headers["location"] == _login_path(client)
        assert _count() == before, "No row may be inserted when logged out"


# --------------------------------------------------------------------------
# GET form
# --------------------------------------------------------------------------


class TestForm:
    def test_get_form_logged_in_returns_200(self, auth_client):
        response = auth_client.get(_add_path(auth_client))
        assert response.status_code == 200

    @pytest.mark.parametrize("category", ALL_CATEGORIES)
    def test_get_form_lists_each_category(self, auth_client, category):
        html = auth_client.get(_add_path(auth_client)).text
        assert category in html, f"Category {category} missing from form"

    def test_get_form_defaults_date_to_today(self, auth_client):
        html = auth_client.get(_add_path(auth_client)).text
        assert date.today().isoformat() in html

    def test_get_form_has_expected_fields_and_cancel_link(self, auth_client):
        html = auth_client.get(_add_path(auth_client)).text
        for name in ("amount", "category", "date", "description"):
            assert f'name="{name}"' in html, f"Missing field {name}"
        assert _profile_path(auth_client) in html, "Cancel link to profile expected"


# --------------------------------------------------------------------------
# Successful creation
# --------------------------------------------------------------------------


class TestCreateSuccess:
    def test_post_valid_redirects_to_profile(self, auth_client):
        response = _post(auth_client, **_valid())
        assert response.status_code == 303
        assert response.headers["location"] == _profile_path(auth_client)

    def test_post_valid_inserts_row_with_session_user_and_values(
        self, auth_client, demo_id
    ):
        before = _count()
        _post(auth_client, **_valid())
        assert _count() == before + 1
        row = _latest()
        assert row["user_id"] == demo_id
        assert isinstance(row["amount"], (int, float))
        assert row["amount"] == pytest.approx(12.50)
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-15"
        assert row["description"] == "Lunch"

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_post_blank_description_stored_as_null(self, auth_client, blank):
        _post(auth_client, **_valid(description=blank))
        assert _latest()["description"] is None

    def test_post_missing_description_field_stored_as_null(self, auth_client):
        data = _valid()
        del data["description"]
        response = _post(auth_client, **data)
        assert response.status_code == 303
        assert _latest()["description"] is None

    def test_post_description_is_stripped(self, auth_client):
        _post(auth_client, **_valid(description="  padded  "))
        assert _latest()["description"] == "padded"

    def test_post_future_date_is_allowed(self, auth_client):
        response = _post(auth_client, **_valid(date="2999-01-01"))
        assert response.status_code == 303
        assert _latest()["date"] == "2999-01-01"

    @pytest.mark.parametrize("category", ALL_CATEGORIES)
    def test_post_each_category_accepted(self, auth_client, category):
        response = _post(auth_client, **_valid(category=category))
        assert response.status_code == 303
        assert _latest()["category"] == category

    def test_post_valid_new_expense_appears_on_profile(self, auth_client):
        _post(auth_client, **_valid(description="UniqueMarkerXyz"))
        html = auth_client.get(_profile_path(auth_client)).text
        assert "UniqueMarkerXyz" in html

    @pytest.mark.parametrize("amount,expected", [("0.01", 0.01), ("1000000", 1000000)])
    def test_post_boundary_amounts_accepted(self, auth_client, amount, expected):
        response = _post(auth_client, **_valid(amount=amount))
        assert response.status_code == 303
        assert _latest()["amount"] == pytest.approx(expected)

    def test_post_user_id_form_field_is_ignored(self, auth_client, demo_id):
        other_id = db.create_user("Other", "other@example.com", "secret123")
        assert other_id != demo_id
        _post(auth_client, **_valid(user_id=str(other_id)))
        assert _latest()["user_id"] == demo_id
        with closing(db.get_db()) as conn:
            owned = conn.execute(
                "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (other_id,)
            ).fetchone()[0]
        assert owned == 0, "Other user must not receive the expense"


# --------------------------------------------------------------------------
# Validation failures
# --------------------------------------------------------------------------


class TestValidationFailures:
    def _assert_rejected(self, client, **overrides):
        before = _count()
        response = _post(client, **_valid(**overrides))
        assert response.status_code == 400, f"Expected 400 for {overrides}"
        assert _count() == before, f"No row may be inserted for {overrides}"
        return response

    @pytest.mark.parametrize(
        "amount",
        ["", "0", "-5", "abc", "nan", "inf", "1000000.01", "1.234", "1e400"],
    )
    def test_post_invalid_amount_returns_400_and_inserts_nothing(
        self, auth_client, amount
    ):
        self._assert_rejected(auth_client, amount=amount)

    def test_post_missing_amount_field_returns_400(self, auth_client):
        before = _count()
        data = _valid()
        del data["amount"]
        response = _post(auth_client, **data)
        assert response.status_code == 400
        assert _count() == before

    @pytest.mark.parametrize("category", ["", "Groceries", "food", "Food; DROP TABLE"])
    def test_post_invalid_category_returns_400(self, auth_client, category):
        self._assert_rejected(auth_client, category=category)

    @pytest.mark.parametrize("bad_date", ["2026-02-30", "abc", "26-1-1", ""])
    def test_post_invalid_date_returns_400(self, auth_client, bad_date):
        self._assert_rejected(auth_client, date=bad_date)

    def test_post_description_200_chars_accepted(self, auth_client):
        response = _post(auth_client, **_valid(description="a" * 200))
        assert response.status_code == 303
        assert _latest()["description"] == "a" * 200

    def test_post_description_201_chars_rejected(self, auth_client):
        self._assert_rejected(auth_client, description="a" * 201)

    def test_post_failure_rerenders_form_with_error_and_preserved_values(
        self, auth_client
    ):
        response = self._assert_rejected(
            auth_client, amount="abc", description="KeepMe", category="Bills"
        )
        html = response.text
        assert 'name="amount"' in html, "Form should be re-rendered"
        assert "KeepMe" in html, "Entered description should be preserved"
        assert "2026-03-15" in html, "Entered date should be preserved"
        assert "abc" in html, "Entered amount should be preserved"

    def test_post_sql_injection_in_description_stored_literally(self, auth_client):
        payload = "x'); DROP TABLE expenses;--"
        response = _post(auth_client, **_valid(description=payload))
        assert response.status_code == 303
        assert _latest()["description"] == payload
        assert _count() > 0


# --------------------------------------------------------------------------
# XSS
# --------------------------------------------------------------------------


class TestEscaping:
    def test_script_description_rendered_escaped_on_profile(self, auth_client):
        payload = "<script>alert(1)</script>"
        response = _post(auth_client, **_valid(description=payload))
        assert response.status_code == 303
        html = auth_client.get(_profile_path(auth_client)).text
        assert payload not in html, "Raw <script> must not appear in profile"
        assert "&lt;script&gt;" in html, "Description should be HTML-escaped"
