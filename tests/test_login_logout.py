import re

import auth
from database import db

DEMO_EMAIL = "demo@expensetrack.com"
DEMO_PASSWORD = "demo123"
GENERIC_ERROR = "Invalid email or password."


def _login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def _demo_id():
    return db.get_user_by_email(DEMO_EMAIL)["id"]


def test_get_login_renders_form(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert re.search(r'action="[^"]*/login"', response.text)


def test_login_success_sets_httponly_cookie(client):
    response = _login(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/profile"
    set_cookie = response.headers["set-cookie"].lower()
    assert "session=" in set_cookie
    assert "httponly" in set_cookie


def test_login_email_case_and_whitespace_insensitive(client):
    response = _login(client, email="  Demo@ExpenseTrack.com ")
    assert response.status_code == 303


def test_wrong_password_and_unknown_email_same_error(client):
    wrong_pw = _login(client, password="wrong-password")
    unknown = _login(client, email="nobody@example.com")
    for response in (wrong_pw, unknown):
        assert response.status_code == 400
        assert GENERIC_ERROR in response.text
        assert "set-cookie" not in response.headers


def test_empty_fields_show_generic_error(client):
    for email, password in (("", ""), (DEMO_EMAIL, ""), ("", DEMO_PASSWORD)):
        response = _login(client, email=email, password=password)
        assert response.status_code == 400
        assert GENERIC_ERROR in response.text


def test_failed_login_keeps_email_not_password(client):
    response = _login(client, email="keep@example.com", password="secret-pw-1")
    assert 'value="keep@example.com"' in response.text
    assert "secret-pw-1" not in response.text


def test_registered_user_can_log_in(client):
    client.post(
        "/register",
        data={
            "name": "Ann Lee",
            "email": "ann@example.com",
            "password": "longenough1",
            "confirm_password": "longenough1",
        },
    )
    response = _login(client, email="ann@example.com", password="longenough1")
    assert response.status_code == 303


def test_navbar_logged_out_and_logged_in(client):
    page = client.get("/").text
    assert "Sign in" in page and "Get started" in page
    assert "Sign out" not in page

    _login(client)
    page = client.get("/").text
    assert "Sign out" in page
    assert "Demo User" in page
    assert "Sign in" not in page and "Get started" not in page


def test_login_page_redirects_when_logged_in(client):
    _login(client)
    response = client.get("/login")
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_logout_clears_cookie_and_logs_out(client):
    _login(client)
    response = client.get("/logout")
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session=" in response.headers["set-cookie"].lower()
    page = client.get("/").text
    assert "Sign in" in page and "Sign out" not in page


def test_logout_when_logged_out_is_harmless(client):
    assert client.get("/logout").status_code == 303


def test_tampered_cookie_is_logged_out(client):
    client.cookies.set("session", f"{_demo_id()}.deadbeef")
    page = client.get("/")
    assert page.status_code == 200
    assert "Sign in" in page.text


def test_malformed_cookies_are_logged_out(client):
    for value in ("garbage", "abc.def", ".", "1."):
        client.cookies.set("session", value)
        response = client.get("/")
        assert response.status_code == 200
        assert "Sign out" not in response.text


def test_cookie_for_missing_user_is_logged_out(client):
    client.cookies.set("session", auth.sign_session(99999))
    page = client.get("/")
    assert page.status_code == 200
    assert "Sign out" not in page.text


def test_other_stubs_unchanged(client):
    profile = client.get("/profile")
    assert profile.status_code == 303
    assert profile.headers["location"] == "/login"
    logout = client.get("/logout")
    assert logout.status_code == 303
    assert "coming in Step 3" not in logout.text


def test_auth_pages_redirect_when_logged_in(client):
    _login(client)
    for path in ("/login", "/register"):
        response = client.get(path)
        assert response.status_code == 303, path
        assert response.headers["location"] == "/"
    for path in ("/login", "/register"):
        response = client.post(path, data={})
        assert response.status_code == 303, path
        assert response.headers["location"] == "/"
