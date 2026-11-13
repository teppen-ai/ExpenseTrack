# Spec: Registration

## Overview
Make the existing `/register` page functional. Today `GET /register` only renders a form whose `POST /register` target does not exist. This step adds the POST handler that validates the submitted name, email and password, stores a new user with a hashed password, on success the user is shown with a success message and sends the user to the login page. It is the first write path into the `users` table (created and seeded in the database-setup step) and is the prerequisite for login in Step 3. No session handling is added here.

## Depends on
- Database setup (`users` table, `get_db()`, `init_db()`, `pwdlib` hashing) — complete.

## Routes
- `GET /register` — render the registration form (already implemented, modified to pass form state back) — public
- `POST /register` — validate form fields, create the user, redirect to `/login` with status 303 on success; re-render `register.html` with an `error` message and HTTP 400 on failure — public

No other new routes. Stub routes (`/logout`, `/profile`, `/expenses/*`) must stay untouched.

## Database changes
No schema changes. The existing `users` table already has everything needed (`name`, `email UNIQUE`, `password_hash`, `created_at`).

New helpers in `database/db.py` (DB logic must not live in the route):
- `get_user_by_email(email)` — return the matching `sqlite3.Row` or `None` (parameterized, email compared case-insensitively via normalised lowercase storage).
- `create_user(name, email, password)` — hash the password with `PasswordHash.recommended().hash()`, insert the row, return the new `id`. Let `sqlite3.IntegrityError` from the UNIQUE constraint propagate so the route can handle a race on duplicate email.

## Templates
- **Create:** none
- **Modify:** `templates/register.html`
  - Change `action="/register"` to `action="{{ url_for('register') }}"` (no hardcoded URLs).
  - Re-populate `name` and `email` inputs from template variables after a failed submit (never re-populate the password).
  - Keep the existing `{% if error %}` block for messages.

## Files to change
- `app.py` — add `POST /register`; pass `name`/`email`/`error` context on re-render
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `templates/register.html` — `url_for` action and field re-population
- `tests/` — add registration tests (see below)

## Files to create
- `tests/test_registration.py`

## New dependencies
No new dependencies.

Note: FastAPI's `Form(...)` requires `python-multipart`, which is **not** in `requirements.txt` and is not installed. Do not add it. Read the urlencoded body with `await request.body()` and parse it using `urllib.parse.parse_qs` from the standard library inside the route (the route must be `async def`).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with `pwdlib` (`PasswordHash.recommended()`), consistent with `seed_db()`. The generic template rule says werkzeug, but werkzeug is not a dependency of this FastAPI project, so `pwdlib` is the correct choice
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `url_for()` for every internal link and redirect target
- Use `abort()` / proper status codes for HTTP errors; no bare error-string returns
- Route stays thin: parse input, call db helpers, render or redirect
- Validation (server-side, do not rely on the HTML `required` attribute):
  - name: trimmed, non-empty
  - email: trimmed, lowercased, non-empty, contains `@` with text on both sides
  - password: at least 8 characters (matches the form placeholder)
- Duplicate email must show a friendly error, never a 500 — check first, and also catch `sqlite3.IntegrityError`
- Never log or echo the password; never store it in plain text
- Do not create a session or log the user in (that is Step 3)

## Definition of done
- [ ] `GET /register` still renders the form with status 200
- [ ] Submitting valid name, a new email and an 8+ character password redirects (303) to `/login`
- [ ] A new row exists in `users` and `password_hash` is an argon2 hash, not the plain password
- [ ] The new user's password verifies against the stored hash with `pwdlib`
- [ ] Registering with an email that already exists (including `Demo@ExpenseTrack.com` vs the seeded demo user) re-renders the form with a duplicate-email error and creates no second row
- [ ] A password shorter than 8 characters re-renders with an error and creates no row
- [ ] An empty/whitespace-only name or an invalid email re-renders with an error and creates no row
- [ ] After a failed submit the name and email fields keep their values; the password field is empty
- [ ] The form `action` is generated with `url_for`, and no hardcoded `/register` or `/login` URLs were added
- [ ] The app starts on port 8001 without errors and no new packages were added to `requirements.txt`
- [ ] `pytest` passes, including the new `tests/test_registration.py`
