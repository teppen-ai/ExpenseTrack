import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash

from database import db

ROOT = Path(__file__).resolve().parent.parent
DUPLICATE_ERROR = "already exists"


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    return db.DB_PATH


@pytest.fixture
def client(temp_db):
    from app import app  # imported after DB_PATH is patched

    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


def _query(sql, params=()):
    conn = db.get_db()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _user_count():
    return _query("SELECT COUNT(*) AS n FROM users")[0]["n"]


def _register(client, name="Ann Lee", email="ann@example.com",
              password="longenough1", confirm_password=None):
    if confirm_password is None:
        confirm_password = password
    return client.post(
        "/register",
        data={
            "name": name,
            "email": email,
            "password": password,
            "confirm_password": confirm_password,
        },
    )


def test_get_register_returns_form(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert 'name="email"' in response.text
    # url_for renders an absolute URL under TestClient, so match the suffix.
    assert re.search(r'action="[^"]*/register"', response.text)


def test_register_success_redirects_to_login(client):
    response = _register(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_register_creates_user_with_hashed_password(client):
    _register(client, password="longenough1")
    rows = _query("SELECT * FROM users WHERE email = ?", ("ann@example.com",))
    assert len(rows) == 1
    assert rows[0]["name"] == "Ann Lee"
    assert rows[0]["password_hash"] != "longenough1"
    assert rows[0]["password_hash"].startswith("$argon2")


def test_registered_password_verifies(client):
    _register(client, password="longenough1")
    stored = _query(
        "SELECT password_hash FROM users WHERE email = ?", ("ann@example.com",)
    )[0]["password_hash"]
    assert PasswordHash.recommended().verify("longenough1", stored)


def test_email_is_stored_lowercase(client):
    _register(client, email="  New@Example.COM ")
    rows = _query("SELECT email FROM users WHERE email = ?", ("new@example.com",))
    assert len(rows) == 1


@pytest.mark.parametrize(
    "email",
    ["demo@expensetrack.com", "Demo@ExpenseTrack.com", "  demo@expensetrack.com "],
)
def test_register_duplicate_email_rejected(client, email):
    before = _user_count()
    response = _register(client, email=email)
    assert response.status_code == 400
    assert DUPLICATE_ERROR in response.text
    assert _user_count() == before


def test_register_same_email_twice_rejected(client):
    assert _register(client).status_code == 303
    response = _register(client)
    assert response.status_code == 400
    assert DUPLICATE_ERROR in response.text


def test_integrity_error_path_shows_duplicate_error(client, monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "get_user_by_email", lambda email: None)
    before = _user_count()
    response = _register(client, email="demo@expensetrack.com")
    assert response.status_code == 400
    assert DUPLICATE_ERROR in response.text
    assert _user_count() == before


def test_register_short_password_rejected(client):
    before = _user_count()
    response = _register(client, password="short")
    assert response.status_code == 400
    assert "at least 8 characters" in response.text
    assert _user_count() == before


def test_register_password_mismatch_rejected(client):
    before = _user_count()
    response = _register(
        client, password="longenough1", confirm_password="different123"
    )
    assert response.status_code == 400
    assert "Passwords do not match." in response.text
    assert 'value="ann@example.com"' in response.text
    assert _user_count() == before


def test_register_missing_confirm_password_rejected(client):
    before = _user_count()
    response = client.post(
        "/register",
        data={"name": "Ann", "email": "ann@example.com",
              "password": "longenough1"},
    )
    assert response.status_code == 400
    assert "Passwords do not match." in response.text
    assert _user_count() == before


def test_get_register_has_confirm_password_field(client):
    response = client.get("/register")
    assert 'name="confirm_password"' in response.text


@pytest.mark.parametrize("name", ["", "   "])
def test_register_invalid_name_rejected(client, name):
    before = _user_count()
    response = _register(client, name=name)
    assert response.status_code == 400
    assert "enter your name" in response.text
    assert _user_count() == before


@pytest.mark.parametrize(
    "email", ["", "nope", "@x.com", "a@", "a@b@c", "a b@c.com"]
)
def test_register_invalid_email_rejected(client, email):
    before = _user_count()
    response = _register(client, email=email)
    assert response.status_code == 400
    assert "valid email" in response.text
    assert _user_count() == before


def test_empty_body_returns_400_not_500(client):
    before = _user_count()
    response = client.post("/register", content=b"")
    assert response.status_code == 400
    assert _user_count() == before


def test_failed_submit_repopulates_fields_but_not_password(client):
    response = _register(
        client, name="Ann Lee", email="ann@example.com", password="short"
    )
    assert response.status_code == 400
    assert 'value="Ann Lee"' in response.text
    assert 'value="ann@example.com"' in response.text
    assert "short" not in response.text.replace("Password must be", "")
    password_input = response.text.split('id="password"')[1].split(">")[0]
    assert "value=" not in password_input


def test_html_in_name_is_escaped(client):
    response = _register(client, name="<script>x</script>", password="short")
    assert "<script>x</script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_register_template_uses_url_for():
    source = (ROOT / "templates" / "register.html").read_text(encoding="utf-8")
    assert "url_for('register')" in source
    assert 'action="/register"' not in source


def test_requirements_do_not_add_multipart():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "multipart" not in requirements.lower()
