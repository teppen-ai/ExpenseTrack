# Spec: Login and Logout

## Overview
Make the existing `/login` page functional and replace the `/logout` stub. `POST /login` verifies an email and password against the `users` table (populated by registration and the seeded demo user), then starts a session by setting a signed cookie and redirecting to the landing page (the `/profile` page does not exist until Step 4). `GET /logout` clears the session and redirects to the landing page. The navbar becomes session-aware, showing "Sign out" instead of "Sign in / Get started" when logged in. This is the first step that establishes who the current user is, and is the prerequisite for the protected pages in Steps 4–9.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `pwdlib` hashing, seeded demo user) — complete.
- Step 2 — Registration (`get_user_by_email()`, `create_user()`, redirect to `/login`) — complete.

## Routes
- `GET /login` — render the login form (already implemented); if the user is already logged in, redirect (303) to `/` — public
- `POST /login` — read email and password, verify credentials, set the session cookie and redirect (303) to `/` on success; re-render `login.html` with an `error` and HTTP 400 on failure — public
- `GET /logout` — clear the session cookie and redirect (303) to `/` — public (harmless when not logged in)

No other new routes. Stub routes (`/profile`, `/expenses/*`) must stay untouched.

## Database changes
No schema changes. The existing `users` table has everything needed.

New helper in `database/db.py`:
- `get_user_by_id(user_id)` — return the matching `sqlite3.Row` or `None` (parameterized). Used to resolve the current user from the session.
- `verify_user(email, password)` — look up the user via `get_user_by_email()`, check the password with `PasswordHash.recommended().verify(password, row["password_hash"])`, return the user row or `None`. When the email is unknown, still run a dummy hash verification so response time does not reveal whether the email exists.

## Session handling
`itsdangerous` is **not** installed, so Starlette's `SessionMiddleware` cannot be used and no package may be added. Implement a minimal signed-cookie session using the standard library (`hmac`, `hashlib`, `secrets`):
- Cookie name `session`, value `<user_id>.<hmac_sha256_hex>` signed with a secret key.
- Secret key read from the `SECRET_KEY` environment variable; fall back to a random per-process key generated with `secrets.token_hex(32)` (sessions then reset on restart — acceptable for dev, and documented in a code comment).
- Cookie flags: `httponly=True`, `samesite="lax"`, `path="/"`, session-lifetime (no `max_age`).
- Compare signatures with `hmac.compare_digest`.
- A helper `get_current_user(request)` returns the user row or `None` if the cookie is missing, malformed, badly signed, or the user no longer exists.
- Session helpers live in a new module `auth.py` (signing/verification only — no DB queries inside; the DB lookup uses `get_user_by_id()`).

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — change `action="/login"` to `action="{{ url_for('login') }}"`; re-populate the `email` input from a template variable after a failed submit (never the password); keep the existing `{% if error %}` block.
  - `templates/base.html` — when `current_user` is set, the nav shows a "Sign out" link (`url_for('logout')`) and the user's name instead of "Sign in" / "Get started". Replace the hardcoded `/terms` and `/privacy` footer links with `url_for('terms')` / `url_for('privacy')`.
  - `templates/register.html` and `templates/landing.html` — only if they hardcode URLs encountered while wiring this up; otherwise untouched.

Every `TemplateResponse` for pages using `base.html` must receive `current_user` so the navbar renders correctly (see Rules).

## Files to change
- `app.py` — add `POST /login`, real `/logout`, redirect-if-logged-in on `GET /login`, pass `current_user` to templates
- `database/db.py` — add `get_user_by_id()` and `verify_user()`
- `templates/login.html` — `url_for` action and email re-population
- `templates/base.html` — session-aware nav, `url_for` footer links
- `static/css/style.css` — styling for the nav user name / sign-out link, using existing CSS variables

## Files to create
- `auth.py` — signed-cookie session helpers
- `tests/test_login_logout.py`

## New dependencies
No new dependencies. Do not add `itsdangerous` or `python-multipart`; parse the urlencoded body with `await request.body()` and `urllib.parse.parse_qs` as in `POST /register`, so the route must be `async def`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords verified with `pwdlib` (`PasswordHash.recommended().verify`), consistent with `create_user()` and `seed_db()`. The generic template rule says werkzeug, but werkzeug is not a dependency of this FastAPI project
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `url_for()` for every internal link and redirect target
- Use `abort()` / proper status codes for HTTP errors; no bare error-string returns. `/logout` must render nothing — it redirects
- Routes stay thin: parse input, call db/auth helpers, render or redirect
- Email is trimmed and lowercased before lookup
- Use one generic error for both unknown email and wrong password: "Invalid email or password." Never reveal which was wrong
- Empty email or password re-renders with the same generic error (HTTP 400), not a 500
- Never log or echo the password; never re-populate it
- Do not implement `/profile` or any other stub route; post-login redirect goes to `/`
- Do not change the port (8001)
- To avoid passing `current_user` in every route by hand, expose it through a small helper or Jinja global rather than duplicating lookup code per route

## Definition of done
- [ ] `GET /login` renders the form with status 200 when logged out
- [ ] Logging in as `demo@expensetrack.com` / `demo123` returns 303 to `/` and sets an HttpOnly `session` cookie
- [ ] Email matching is case-insensitive and ignores surrounding whitespace (`  Demo@ExpenseTrack.com `)
- [ ] A wrong password re-renders the login form with "Invalid email or password." and status 400, and sets no cookie
- [ ] An unknown email shows the exact same message as a wrong password
- [ ] Empty email or password shows the generic error, not a 500
- [ ] After a failed login the email field keeps its value; the password field is empty
- [ ] A user created through `/register` can log in with the password they chose
- [ ] When logged in, the navbar shows the user's name and a "Sign out" link, and no "Sign in" / "Get started" links
- [ ] When logged out, the navbar shows "Sign in" and "Get started"
- [ ] Visiting `/login` while logged in redirects (303) to `/`
- [ ] `GET /logout` returns 303 to `/` and clears the `session` cookie; the navbar shows the logged-out state afterwards
- [ ] A tampered or unsigned `session` cookie is treated as logged out (no 500)
- [ ] A `session` cookie for a user id that no longer exists is treated as logged out
- [ ] `/logout` no longer returns the plain-text stub; `/profile` and `/expenses/*` stubs are unchanged
- [ ] No hardcoded internal URLs remain in `login.html` or `base.html`
- [ ] The app starts on port 8001 without errors and `requirements.txt` is unchanged
- [ ] `pytest` passes, including the new `tests/test_login_logout.py`
