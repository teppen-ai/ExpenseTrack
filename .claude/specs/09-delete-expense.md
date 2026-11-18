# Spec: Delete Expense

## Overview
Step 9 lets a logged-in user permanently remove an expense. Each row in the profile transaction list gets a "Delete" button next to "Edit". Clicking it shows a browser confirmation dialog; on confirm, the row's form POSTs and the user is redirected back to `/profile`. No separate page is opened. Deletion is POST-only so links, prefetch or crawlers can never destroy data.

## Depends on
- Step 1: Database setup
- Step 3: Login / Logout (`get_current_user`)
- Step 4-6: Profile page (transaction list, redirect target)
- Step 8: Edit expense (`_login_redirect`, `id` in `get_recent_transactions`, actions column)

## Routes
- `POST /expenses/{id}/delete` — delete the expense and redirect (303) to `/profile` — logged-in, owner only

Behaviour:
- Unauthenticated requests redirect (303) to `/login`.
- Missing or not-owned expense: 404 (indistinguishable). Ownership enforced in SQL `WHERE id = ? AND user_id = ?`.
- The old `GET /expenses/{id}/delete` stub is removed (GET returns 405).
- No form fields are read.

## Database changes
No schema changes. Add `delete_expense(expense_id, user_id)` in `database/db.py` (parameterised DELETE, returns True if a row was removed).

## Templates
- **Create:** none.
- **Modify:** `templates/profile.html` — Delete button (inside a POST form with `data-confirm`) next to Edit in each row.

## Files to change
- `app.py`, `database/db.py`, `templates/profile.html`, `static/css/profile.css`, `static/js/main.js` (generic `data-confirm` submit handler), `CLAUDE.md`

## Files to create
- `tests/test_09-delete-expense.py` — via `/test-feature`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs; parameterised queries only
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`; `url_for()` for every link and form action
- DB logic in `database/db.py`; `abort`/`HTTPException(404)` for missing expenses
- Vanilla JS only
- Deletion only via POST

## Definition of done
- [ ] Each `/profile` row shows a Delete button next to Edit
- [ ] Clicking Delete shows a confirm dialog; Cancel keeps the expense and stays on `/profile`
- [ ] Confirming redirects to `/profile`; the expense is gone from the list, totals and breakdown
- [ ] Row count drops by exactly one; other expenses unchanged
- [ ] Logged out POST redirects to `/login` and deletes nothing
- [ ] Missing id or another user's expense returns 404 and nothing is deleted; repeat POST returns 404
- [ ] GET `/expenses/{id}/delete` returns 405
- [ ] No hardcoded hex colours or URLs; `pytest` passes
