# Spec: Edit Expense

## Overview
Step 8 lets a logged-in user change an expense they previously recorded. Each row in the profile transaction list gets an "Edit" link that opens a form pre-filled with the expense's current amount, category, date and description. Submitting valid data updates the row and redirects to `/profile`; invalid data re-renders the form with an error and the entered values. This replaces the plain-text "coming in Step 8" stub and is the first update path for expense data, building on the add-expense form and validation from Step 7.

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES` constant)
- Step 3: Login / Logout (session cookie, `get_current_user`)
- Step 4-6: Profile page (transaction list that hosts the Edit links; redirect target)
- Step 7: Add expense (`_validate_expense`, form template and CSS to reuse)

## Routes
- `GET /expenses/{id}/edit` — render the expense form pre-filled with the stored values — logged-in, owner only
- `POST /expenses/{id}/edit` — validate the form and update the expense; on success redirect (303) to `/profile`; on validation failure re-render the form with status 400, an error message and the entered values preserved — logged-in, owner only

Behaviour:
- Unauthenticated requests to either method redirect (303) to `/login` (reuse `_login_redirect`, which also clears a cookie pointing at a missing user).
- If the expense does not exist **or belongs to another user**, respond with `abort(404)` for both methods (no distinction, so ids of other users' expenses are not revealed). Nothing is modified.
- `id` is an `int` path parameter; a non-integer id yields FastAPI's standard 422/404 handling.
- Form body parsed with `parse_qs` as in `/expenses/add`.
- Validation reuses `_validate_expense` unchanged (same rules as add: amount, category, strict date, description ≤ 200, blank description stored as `NULL`).
- `user_id` is never read from the form; ownership is enforced in the SQL `WHERE id = ? AND user_id = ?`.
- Stored date is pre-filled in ISO form; amount is pre-filled without float noise (e.g. `12.5`, not `12.500000001`).
- `GET /expenses/{id}/delete` is **not** touched and remains a stub.

## Database changes
No schema changes. Add two helpers in `database/db.py`:
- `get_expense(expense_id, user_id)` — parameterised `SELECT` filtered by both id and user_id; returns the row or `None`.
- `update_expense(expense_id, user_id, amount, category, date, description)` — parameterised `UPDATE ... WHERE id = ? AND user_id = ?`; returns `True` if a row was updated, else `False`.

Also extend `get_recent_transactions` in `database/queries.py` to include `id` in its SELECT and returned dicts so the profile template can build Edit links.

## Templates
- **Create:** none. Reuse `templates/add_expense.html` rather than duplicating the form.
- **Modify:**
  - `templates/add_expense.html` — make title, heading, subtitle, form `action` and submit-button label depend on context variables (e.g. `form_action`, `page_title`, `submit_label`) so the same template serves add and edit; the add page output must stay identical. Form action built with `url_for()`.
  - `templates/profile.html` — add an "Actions" column header and an "Edit" link per transaction row pointing to `url_for('edit_expense', id=t.id)`; update the empty-state `colspan` from 4 to 5.

## Files to change
- `app.py` — replace the `GET /expenses/{id}/edit` stub with real GET and POST routes; import `get_expense` and `update_expense`; generalise `_expense_form_response` to accept the form action and labels
- `database/db.py` — add `get_expense`, `update_expense`
- `database/queries.py` — include `id` in `get_recent_transactions`
- `templates/add_expense.html` — context-driven labels/action (see above)
- `templates/profile.html` — Edit link column
- `static/css/profile.css` — style for the Edit link / actions column (CSS variables only)
- `CLAUDE.md` — mark `GET /expenses/<id>/edit` as Implemented and add a `POST /expenses/<id>/edit` row

## Files to create
- `tests/test_edit_expense.py` — via `/test-feature`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with the existing `pwdlib` helpers (no password handling in this step; the generic "werkzeug" rule does not apply since the project uses pwdlib)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py`, not in the route
- Use `url_for()` for every internal link and form action
- Use `abort(404)` for missing / not-owned expenses, not raw string returns
- Do NOT implement `/expenses/{id}/delete`; it stays a stub
- Vanilla JS only (none required)
- Jinja2 autoescaping must stay on so descriptions cannot inject HTML
- Do not modify `expense_tracker.db` schema or commit the existing uncommitted db/backup files as part of this feature

## Definition of done
- [ ] Each row on `/profile` shows an "Edit" link that opens `/expenses/{id}/edit`; the empty-state row still spans the full table width
- [ ] Logged out, GET and POST on `/expenses/{id}/edit` redirect to `/login` and change nothing
- [ ] Logged in as the owner, the edit page renders pre-filled with the expense's current amount, category (selected), date and description, with a clear "Edit expense" title and a Cancel link to `/profile`
- [ ] Submitting valid changes redirects to `/profile` and the updated values appear in the transaction list, totals and category breakdown
- [ ] Clearing the description stores `NULL` and the row displays "—"
- [ ] Invalid amount, category, date or over-long description re-renders the form with status 400, an error and the entered values preserved; the stored row is unchanged
- [ ] Editing a non-existent id returns 404 (GET and POST)
- [ ] Editing another user's expense returns 404 (GET and POST) and that expense is unchanged; `user_id` cannot be changed via the form
- [ ] The edit does not create a new row (row count unchanged) and `created_at` is preserved
- [ ] A description containing `<script>` renders escaped on the edit form
- [ ] `/expenses/add` still looks and behaves as before (title, button label "Add expense", action)
- [ ] `/expenses/{id}/delete` still returns its stub response
- [ ] No hardcoded hex colours or hardcoded URLs in changed templates/CSS; `pytest` passes
