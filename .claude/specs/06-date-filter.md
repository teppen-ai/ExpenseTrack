# Spec: Date Filter for Profile Page

## Overview
Step 6 lets a logged-in user narrow the profile page to a date range. A compact
filter bar (quick-select pills "All Time", "This Month", "Last 3 Months" and
"Last 6 Months", then From / To date inputs and an Apply button) submits via
GET query parameters `start` and `end`. The summary stats, transaction list and category
breakdown all respect the selected range, so the three sections always describe
the same set of expenses. With no filter the page behaves exactly as it does
today. This builds on the live-data profile from Step 5 and is the first
interactive control on that page.

## Depends on
- Step 1: Database setup (`expenses.date` stored as ISO `YYYY-MM-DD` text)
- Step 3: Login / Logout (session cookie, `get_current_user`)
- Step 4: Profile page UI
- Step 5: Backend routes for profile page (`database/queries.py` helpers)

## Routes
No new routes. The existing route is modified:
- `GET /profile?start=YYYY-MM-DD&end=YYYY-MM-DD` — profile page filtered to the
  inclusive date range; both params optional — logged-in

Behaviour:
- Either param may be omitted (open-ended range) or blank (treated as omitted).
- Invalid dates (not `YYYY-MM-DD`, or impossible such as `2026-02-30`) are
  ignored and an inline error message is shown; the page still renders with
  that bound unfiltered (status 200). If the other bound is valid it still
  applies.
- Parsed dates are normalised with `.date().isoformat()` (so `2026-2-3`
  becomes `2026-02-03`) before being used in queries.
- If `start` is after `end`, show an inline error and render unfiltered data;
  the entered values stay in the inputs so the user can fix them.
- Unauthenticated requests still redirect to `/login` (303), with filter
  params dropped.

## Database changes
No database changes. `expenses.date` is already ISO text, so string comparison
(`date >= ?` / `date <= ?`) is correct. No index is added at this stage.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a single-row filter card above the stats: pills on the left, a
    divider, then a GET form (`action` via `url_for('profile')`) with
    `<input type="date" name="start">`, the text "to",
    `<input type="date" name="end">` and an Apply pill. The inputs are
    pre-filled with the active values and have `aria-label`s instead of
    visible From/To labels.
  - Pills: "All Time" links to `url_for('profile')` with no params (this
    replaces a separate Clear link) and is highlighted when no filter is
    active. The other pills are links built as
    `{{ url_for('profile') }}?start=<iso>&end=<iso>` (Starlette `url_for`
    accepts path params only, not query params). The pill matching the active
    range is highlighted. Presets: "This Month" = first to last day of the
    current month; "Last 3 Months" / "Last 6 Months" = the same day of the
    month 3 / 6 months ago (day clamped to the month length, e.g. 31 May ->
    28 Feb) through today.
  - Show an error message element when validation fails. There is no "Showing
    …" range label; the highlighted pill and prefilled inputs show the range.
  - Rename the "Recent transactions" heading to "Transactions" when a filter
    is active; the empty states read "No transactions in this range." and
    "No spending in this range." (breakdown).
  - Never hardcode URLs.

## Files to change
- `app.py` — `profile()` takes optional `start: str | None` and
  `end: str | None` parameters (kept as `str` so bad input gets the inline
  error rather than a 422), passes them through `resolve_date_filter`, hands
  the validated range to the query helpers, and adds `filters` (start, end,
  error, presets) to the template context.
- `database/queries.py` — `get_summary_stats`, `get_recent_transactions` and
  `get_category_breakdown` accept optional `start=None, end=None`
  (keyword-only on `get_recent_transactions`). The SQL is a static clause,
  `user_id = ? AND (? IS NULL OR date >= ?) AND (? IS NULL OR date <= ?)`,
  so no f-strings are used in SQL.
- `templates/profile.html` — as described above; preset links use
  `url_for('profile').include_query_params(start=..., end=...)`.
- `CLAUDE.md` — no route table change needed (no new routes).

## Files to create
- `database/date_range.py` — pure date validation and presets
  (`resolve_date_filter`, plus private helpers); no SQLite.
- `static/css/date-filter.css` — filter bar, pill, date input and
  `.filter-error` styles, linked from the `head` block of `profile.html`.
- `tests/conftest.py` — restored from git (fixtures `temp_db` and `client`).
- `tests/test_date_filter.py` — tests for the filtered query helpers and the
  `/profile` route (written via `/test-feature 06-date-filter`).

## New dependencies
No new dependencies. Filters use GET query params, so `python-multipart` is not
needed.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never f-strings in SQL; dates are always bound
  with `?` (a NULL bound means "no limit")
- Passwords are hashed with `pwdlib` only; this step touches no auth code
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline `<style>` or `style=""`; styles go in `static/css/date-filter.css`
- Vanilla JS only; the feature must work with no JavaScript at all
- DB logic stays in `database/queries.py`, never inline in the route
- Date validation via `datetime.strptime(value, "%Y-%m-%d")`; the inclusive
  range semantics apply to both bounds
- Range filters must apply to stats, transactions and breakdown consistently
- Currency continues to display as ₹
- Do not implement the stub routes (`/expenses/add`, edit, delete)
- Filter scope is always `user_id = ?` — a filter must never expose another
  user's rows
- Preserve the existing limit of 10 on the transaction list unless the spec
  owner decides otherwise; with a filter active the list is still limited to
  the 10 most recent matching rows

## Definition of done
- [ ] `/profile` with no params renders identically to before (8 seed
      transactions, same totals)
- [ ] Choosing From and To dates and clicking Apply updates the URL to
      `/profile?start=...&end=...` and the page shows only expenses in that
      inclusive range
- [ ] Total spent, transaction count, top category, transaction list and
      category breakdown all reflect the filtered set; breakdown percentages
      still sum to 100
- [ ] An expense dated exactly on `start` or exactly on `end` is included
- [ ] Only `start` set shows everything on/after it; only `end` set shows
      everything on/before it
- [ ] A range with no expenses shows ₹0.00, 0 transactions, "—" top category,
      "No transactions in this range." and an empty breakdown, with no errors
- [ ] `start` later than `end` shows an inline error and unfiltered data
- [ ] `?start=banana` and `?start=2026-02-30` show an inline error and do not
      crash (HTTP 200)
- [ ] Date inputs are pre-filled with the active range after submit
- [ ] "All Time" returns to `/profile` with no params and is highlighted when
      no filter is active; each preset pill applies the expected range and is
      highlighted when its range is active
- [ ] Another user's expenses never appear in a filtered view
- [ ] Unauthenticated `GET /profile?start=2026-01-01` redirects to `/login`
- [ ] The filter works with JavaScript disabled and is usable at phone width
- [ ] The filter bar is a single compact row on desktop (pills, divider, date
      inputs, Apply) and wraps without horizontal scroll on narrow screens
- [ ] No hardcoded hex colours or URLs were added
