"""Tests for the GET /analytics "coming soon" page and its navbar link."""

import re

import pytest

DEMO_EMAIL = "demo@expensetrack.com"
DEMO_PASSWORD = "demo123"


def _path(client, name):
    return client.app.url_path_for(name)


def _analytics_link_tag(html):
    """Return the opening <a ...> tag whose text is 'Analytics' in the navbar, or None."""
    for match in re.finditer(r"<a\b[^>]*>\s*Analytics\s*</a>", html):
        return match.group(0)
    return None


@pytest.fixture
def auth_client(client):
    response = client.post(
        _path(client, "login"),
        content=f"email={DEMO_EMAIL}&password={DEMO_PASSWORD}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 303, "Login should redirect with 303"
    return client


class TestAnalyticsAuthGuard:
    def test_get_analytics_logged_out_redirects_to_login(self, client):
        response = client.get(_path(client, "analytics"))
        assert response.status_code == 303, "Expected 303 redirect when logged out"
        assert response.headers["location"].endswith(_path(client, "login")), (
            "Expected redirect to the login route"
        )


class TestAnalyticsPage:
    def test_get_analytics_logged_in_returns_200(self, auth_client):
        response = auth_client.get(_path(auth_client, "analytics"))
        assert response.status_code == 200

    @pytest.mark.parametrize("text", ["Something useful", "is on the way", "In development"])
    def test_get_analytics_logged_in_shows_coming_soon_text(self, auth_client, text):
        response = auth_client.get(_path(auth_client, "analytics"))
        assert text in response.text, f"Expected {text!r} on analytics page"


class TestNavbarAnalyticsLink:
    def test_landing_page_logged_out_has_no_analytics_link(self, client):
        response = client.get(_path(client, "landing"))
        assert response.status_code == 200
        analytics_url = _path(client, "analytics")
        assert f'href="{analytics_url}"' not in response.text, (
            "Logged-out users must not see the analytics link"
        )
        assert _analytics_link_tag(response.text) is None

    def test_profile_logged_in_shows_analytics_link(self, auth_client):
        response = auth_client.get(_path(auth_client, "profile"))
        assert response.status_code == 200
        tag = _analytics_link_tag(response.text)
        assert tag is not None, "Expected an Analytics nav link for logged-in users"
        assert _path(auth_client, "analytics") in tag

    def test_analytics_page_link_has_nav_active_class(self, auth_client):
        response = auth_client.get(_path(auth_client, "analytics"))
        tag = _analytics_link_tag(response.text)
        assert tag is not None, "Expected an Analytics nav link"
        assert "nav-active" in tag, "Analytics link should be active on /analytics"

    def test_profile_page_link_lacks_nav_active_class(self, auth_client):
        response = auth_client.get(_path(auth_client, "profile"))
        tag = _analytics_link_tag(response.text)
        assert tag is not None, "Expected an Analytics nav link"
        assert "nav-active" not in tag, "Analytics link must not be active on /profile"
