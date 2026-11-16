# Spec: Add Expense

## Overview
Step 7 lets a logged-in user record a new expense. A form collects amount,
category, date and an optional description, validates the input server-side and
inserts a row into `expenses` for the current user. On success the user is
redirected to `/profile`, where the new expense appears in the stats,
transaction list and category breakdown. This replaces the plain-text
"coming in Step 7" stub and is the first write path for expense data, building
on the read-only profile from Steps 4-6.

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES` constant)
- Step 3: Login / Logout (session cookie, `get_current_user`)
- Step 4-6: Profile page (redirect target; displays the new expense)

## Routes
- `GET /expenses/add` — render the empty add-expense form (date defaults to today) — logged-in
- `POST /expenses/add` — validate the form and insert the expense; on success redirect (303) to `/profile`; on validation failure re-render the form with status 400, an error message and the entered values preserved — logged-in

Behaviour:
- Unauthenticated requests to either method redirect (303) to `/login`.
- A session whose user no longer exists is treated as unauthenticated (cleared cookie, redirect to `/login`), matching `/profile`.
- Form body is parsed with `parse_qs` as in `/register` (python-multipart is not installed).
- Validation (first failing rule wins, single error message):
  - `amount`: required, plain digits with an optional decimal part (`^[0-9]+(\.[0-9]+)?$`, so `nan`, `inf`, `1e3`, `+5` and non-ASCII digits are rejected), greater than 0, at most 2 decimal places, at most 1,000,000. Stored as a float.
  - `category`: must be one of `CATEGORIES`.
  - `date`: required, strict `YYYY-MM-DD` (unpadded forms such as `26-1-1` and impossible dates such as `2026-02-30` rejected; the lenient `_parse_date` in `database/date_range.py` is not reused); stored normalised via `.isoformat()`. Future dates are allowed.
  - `description`: optional, stripped, max 200 characters; blank is stored as `NULL`.
- `user_id` always comes from the session, never from the form.

## Database changes
No database changes. The existing `expenses` table (`user_id`, `amount`, `category`, `date`, `description`, `created_at`) is sufficient. Add one helper in `database/db.py`:
- `create_expense(user_id, amount, category, date, description)` — parameterised `INSERT`, returns the new id.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; form (`method="post"`, `action` via `url_for('add_expense_post')`) with amount (`type="number" step="0.01" min="0.01"`), category `<select>` populated from `CATEGORIES`, date (`type="date"`), description (`type="text" maxlength="200"`), a submit button and a Cancel link to `url_for('profile')`. Shows `error` inline and re-fills fields from the submitted values.
- **Modify:** `templates/profile.html` — add a "+ Add Expense" `.btn-primary` link pointing to `url_for('add_expense')`, in a heading row beside the "Recent transactions" heading (always visible, including with zero transactions). It navigates to the `/expenses/add` page (no popup).
- `templates/base.html` is **not** changed: the navbar has no Add Expense link.

## Files to change
- `app.py` — replace the `GET /expenses/add` stub with real GET and POST routes; import `CATEGORIES` and `create_expense`; add a `_validate_expense` helper next to `_validate_registration`
- `database/db.py` — add `create_expense`
- `templates/profile.html` — "+ Add Expense" button in the transactions heading row
- `static/css/profile.css` — `.profile-heading-row` flex layout for the heading and button
- `CLAUDE.md` — mark `GET /expenses/add` as Implemented and add a `POST /expenses/add` row in the routes table

## Files to create
- `templates/add_expense.html`
- `static/css/add-expense.css` — page-specific styles (no inline `<style>`): amount/date row, select, actions row, Cancel link, plus a larger card, type and inputs only at `min-width: 1800px` (2K), the same breakpoint as `style.css`; sizes below that are unchanged
- `tests/test_add_expense.py` — via `/test-feature`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords are hashed with the existing `pwdlib` helpers (no password handling is added in this step; the generic "werkzeug" rule does not apply since the project uses pwdlib)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py`, not in the route
- Use `url_for()` for every internal link and form action
- Do NOT implement `/expenses/{id}/edit` or `/expenses/{id}/delete`; they stay stubs
- Use `abort()` for HTTP errors, not raw string returns
- Vanilla JS only (none required; HTML5 validation plus server-side validation)
- Jinja2 autoescaping must stay on so descriptions cannot inject HTML

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`; POSTing while logged out redirects to `/login` and inserts nothing
- [ ] Logged in, `/expenses/add` renders a styled form with amount, category (all 7 categories), date (defaulting to today) and description
- [ ] Submitting valid data redirects to `/profile` and the new expense appears in the transaction list, and totals and category breakdown update
- [ ] The inserted row has the logged-in user's `user_id`, the amount stored as a number, and the ISO date
- [ ] Blank description is stored as `NULL` and displays without error
- [ ] Missing, zero, negative, non-numeric, `nan`/`inf`, over-limit or 3-decimal amounts re-render the form with status 400, an error message and preserved input; no row is inserted
- [ ] An invalid category (e.g. tampered form value) or invalid date (`2026-02-30`, `abc`) is rejected the same way
- [ ] A description over 200 characters is rejected; one containing `<script>` renders escaped
- [ ] Another user's expenses are unaffected and a user cannot set `user_id` via the form
- [ ] A "+ Add Expense" button is visible on the profile page and opens the `/expenses/add` page; the navbar has no Add Expense link; Cancel returns to `/profile`
- [ ] At 1800px width and up the add-expense card is larger; at smaller widths it is unchanged
- [ ] `/expenses/{id}/edit` and `/expenses/{id}/delete` still return their stub responses
- [ ] No hardcoded hex colours or hardcoded URLs in the new template/CSS; `pytest` passes
