# ExpenseTrack

ExpenseTrack is a personal expense tracker built with FastAPI and SQLite. Users can register, record expenses by category, and review their spending on a profile dashboard. Pages are rendered server-side with Jinja2, and the frontend uses plain HTML, CSS and JavaScript with no framework.

This project was built in an AI-assisted development environment, with [Claude Code](https://claude.com/claude-code) assisting during development. See [Development approach](#development-approach) for details.

## Features

- User registration, login and logout, with Argon2 password hashing and signed session cookies
- Add, edit and delete expenses; each user can only access their own records
- Profile dashboard with summary totals, recent transactions and a category breakdown
- Date range filtering on the dashboard
- Analytics page
- Demo account with sample data, created automatically on first startup

## Tech stack

- **Backend:** FastAPI, Uvicorn
- **Database:** SQLite using the standard library `sqlite3` module (no ORM)
- **Templates:** Jinja2
- **Frontend:** Vanilla JavaScript and CSS
- **Testing:** pytest, httpx

## Getting started

Requires Python 3.10 or newer.

```bash
git clone https://github.com/teppen-ai/ExpenseTrack.git
cd ExpenseTrack

python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
uvicorn app:app --reload --port 8001
```

The application is then available at http://localhost:8001. The SQLite database (`expense_tracker.db`) is created automatically on first run.

A demo account is seeded on first startup:

- Email: `demo@expensetrack.com`
- Password: `demo123`

## Configuration

| Variable | Description |
|---|---|
| `SECRET_KEY` | Key used to sign session cookies. If not set, a random key is generated at each startup, so sessions are lost on restart and cannot be shared across workers. Set it explicitly for any non-local deployment. |
| `PORT` | Port used by the `Procfile` on hosting platforms. |

To generate a key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Project structure

```
app.py              Application routes
auth.py             Session cookie helpers
database/
  db.py             Connection, schema, seeding, user and expense helpers
  queries.py        Read-only queries for the profile page
  date_range.py     Date filter logic
templates/          Jinja2 templates (all extend base.html)
static/             Stylesheets and JavaScript
tests/              pytest test suite
```

## Routes

| Method | Path | Authentication |
|---|---|---|
| GET | `/` | No |
| GET, POST | `/register` | No |
| GET, POST | `/login` | No |
| GET | `/logout` | No |
| GET | `/profile` (optional `?start=&end=`) | Required |
| GET | `/analytics` | Required |
| GET, POST | `/expenses/add` | Required |
| GET, POST | `/expenses/{id}/edit` | Required |
| POST | `/expenses/{id}/delete` | Required |
| GET | `/terms`, `/privacy` | No |

Available categories: Food, Transport, Bills, Health, Entertainment, Shopping, Other.

## Testing

```bash
pytest                           # run the full suite
pytest tests/test_analytics.py   # run a single file
pytest -k "edit"                 # run tests matching a name
```

## Deployment

A `Procfile` is included for platforms such as Railway or Heroku. Before deploying:

- Set `SECRET_KEY` to a persistent random value.
- Use a persistent volume for the SQLite file; otherwise data is lost on redeploy.
- Remove or change the password of the demo account on any public instance.

## Development approach

I took help from Claude Code to assist with development. Each feature began as a short specification in `.claude/specs/`, and project conventions are documented in `CLAUDE.md`. Custom agents and commands under `.claude/` support test writing, code review and shipping features.

## Skills demonstrated

- **Backend development:** REST-style routing, form handling and server-side rendering with FastAPI and Jinja2
- **Databases:** SQLite schema design and parameterized queries
- **Security:** Argon2 password hashing, signed session cookies, per-user access control and server-side validation
- **Testing:** pytest test suite covering routes, validation and access control
- **Version control:** Git and GitHub, feature branches, pull requests, merging and conflict resolution, clear commit history
- **Workflow:** spec-driven development, deployment configuration
- **AI-assisted development:** using Claude Code with custom agents and project rules to speed up development

## Contributing

Create a branch from `main`, follow the conventions in `CLAUDE.md`, confirm that `pytest` passes, and open a pull request.

## License

No license has been specified yet.
