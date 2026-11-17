import re
import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from auth import clear_session_cookie, get_current_user, set_session_cookie
from database.db import (  # noqa: F401
    CATEGORIES,
    create_expense,
    create_user,
    get_db,
    get_expense,
    get_user_by_email,
    init_db,
    seed_db,
    update_expense,
    verify_user,
)
from database.date_range import resolve_date_filter
from database.queries import (
    get_category_breakdown,
    get_profile_user,
    get_recent_transactions,
    get_summary_stats,
)

MIN_PASSWORD_LENGTH = 8
MAX_AMOUNT = Decimal("1000000")
MAX_DESCRIPTION_LENGTH = 200


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_db()
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(
    directory="templates",
    context_processors=[lambda request: {"current_user": get_current_user(request)}],
)


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #


def _redirect_home(request: Request):
    """Send an already-logged-in user to the landing page."""
    return RedirectResponse(request.url_for("landing").path, status_code=303)


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(request, "landing.html")


@app.get("/register", response_class=HTMLResponse)
def register(request: Request):
    if get_current_user(request):
        return _redirect_home(request)
    return templates.TemplateResponse(request, "register.html")


def _validate_registration(name, email, password, confirm_password):
    """Return an error message for invalid registration input, else None."""
    if not name:
        return "Please enter your name."
    local, _, domain = email.partition("@")
    if (
        email.count("@") != 1
        or not local
        or not domain
        or any(ch.isspace() for ch in email)
    ):
        return "Please enter a valid email address."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password != confirm_password:
        return "Passwords do not match."
    return None


@app.post("/register", response_class=HTMLResponse)
async def register_post(request: Request):
    if get_current_user(request):
        return _redirect_home(request)
    # python-multipart is not installed, so parse the urlencoded body by hand.
    raw = (await request.body()).decode("utf-8", errors="replace")
    data = parse_qs(raw, keep_blank_values=True)
    name = data.get("name", [""])[0].strip()
    email = data.get("email", [""])[0].strip().lower()
    password = data.get("password", [""])[0]
    confirm_password = data.get("confirm_password", [""])[0]

    error = _validate_registration(name, email, password, confirm_password)
    if error is None:
        if get_user_by_email(email):
            error = "An account with that email already exists."
        else:
            try:
                create_user(name, email, password)
            except sqlite3.IntegrityError:
                error = "An account with that email already exists."

    if error:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": error, "name": name, "email": email},
            status_code=400,
        )
    return RedirectResponse(request.url_for("login").path, status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    if get_current_user(request):
        return _redirect_home(request)
    return templates.TemplateResponse(request, "login.html")


@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request):
    if get_current_user(request):
        return _redirect_home(request)
    raw = (await request.body()).decode("utf-8", errors="replace")
    data = parse_qs(raw, keep_blank_values=True)
    email = data.get("email", [""])[0].strip().lower()
    password = data.get("password", [""])[0]

    user = verify_user(email, password) if email and password else None
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid email or password.", "email": email},
            status_code=400,
        )
    response = RedirectResponse(request.url_for("profile").path, status_code=303)
    set_session_cookie(response, user["id"])
    return response


@app.get("/logout")
def logout(request: Request):
    response = RedirectResponse(request.url_for("landing").path, status_code=303)
    clear_session_cookie(response)
    return response


@app.get("/terms", response_class=HTMLResponse)
def terms(request: Request):
    return templates.TemplateResponse(request, "terms.html")


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return templates.TemplateResponse(request, "privacy.html")


@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request, start: str | None = None, end: str | None = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(request.url_for("login").path, status_code=303)
    profile_user = get_profile_user(user["id"])
    if profile_user is None:
        response = RedirectResponse(request.url_for("login").path, status_code=303)
        clear_session_cookie(response)
        return response
    filters = resolve_date_filter(start, end)
    date_range = {"start": filters["start"], "end": filters["end"]}
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "profile_user": profile_user,
            "filters": filters,
            "stats": get_summary_stats(user["id"], **date_range),
            "transactions": get_recent_transactions(user["id"], **date_range),
            "breakdown": get_category_breakdown(user["id"], **date_range),
        },
    )


@app.get("/analytics", response_class=HTMLResponse)
def analytics(request: Request):
    if not get_current_user(request):
        return RedirectResponse(request.url_for("login").path, status_code=303)
    return templates.TemplateResponse(request, "analytics.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


def _validate_expense(form):
    """Return (error, cleaned) for the add-expense form; one is always None."""
    raw_amount = form.get("amount", "").strip()
    if not raw_amount:
        return "Please enter an amount.", None
    if not re.fullmatch(r"[0-9]+(\.[0-9]+)?", raw_amount):
        return "Amount must be a valid number.", None
    amount = Decimal(raw_amount)
    if amount <= 0:
        return "Amount must be greater than 0.", None
    if amount.normalize().as_tuple().exponent < -2:
        return "Amount can have at most 2 decimal places.", None
    if amount > MAX_AMOUNT:
        return "Amount cannot exceed 1,000,000.", None

    category = form.get("category", "")
    if category not in CATEGORIES:
        return "Please choose a valid category.", None

    raw_date = form.get("date", "").strip()
    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw_date):
            raise ValueError
        expense_date = date.fromisoformat(raw_date)
    except ValueError:
        return "Please enter a valid date.", None

    description = form.get("description", "").strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return (
            f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters.",
            None,
        )

    return None, {
        "amount": float(amount),
        "category": category,
        "date": expense_date.isoformat(),
        "description": description or None,
    }


def _expense_form_response(
    request,
    values,
    error=None,
    status_code=200,
    *,
    form_action=None,
    page_title="Add expense",
    subtitle="Record a new transaction",
    submit_label="Add expense",
):
    if form_action is None:
        form_action = request.url_for("add_expense_post").path
    return templates.TemplateResponse(
        request,
        "add_expense.html",
        {
            "categories": CATEGORIES,
            "values": values,
            "error": error,
            "form_action": form_action,
            "page_title": page_title,
            "subtitle": subtitle,
            "submit_label": submit_label,
        },
        status_code=status_code,
    )


def _edit_form_response(request, expense_id, values, error=None, status_code=200):
    return _expense_form_response(
        request,
        values,
        error,
        status_code,
        form_action=request.url_for("edit_expense_post", id=expense_id).path,
        page_title="Edit expense",
        subtitle="Update this transaction",
        submit_label="Save changes",
    )


def _format_amount(amount):
    """Format a stored amount for the number input without float noise."""
    return f"{Decimal(str(amount)):f}"


def _login_redirect(request):
    """Redirect to login, clearing the cookie if it points at a missing user."""
    response = RedirectResponse(request.url_for("login").path, status_code=303)
    if request.cookies:
        clear_session_cookie(response)
    return response


@app.get("/expenses/add", response_class=HTMLResponse)
def add_expense(request: Request):
    if not get_current_user(request):
        return _login_redirect(request)
    values = {
        "amount": "",
        "category": "",
        "date": date.today().isoformat(),
        "description": "",
    }
    return _expense_form_response(request, values)


@app.post("/expenses/add", response_class=HTMLResponse)
async def add_expense_post(request: Request):
    user = get_current_user(request)
    if not user:
        return _login_redirect(request)
    raw = (await request.body()).decode("utf-8", errors="replace")
    data = parse_qs(raw, keep_blank_values=True)
    form = {
        key: data.get(key, [""])[0]
        for key in ("amount", "category", "date", "description")
    }

    error, cleaned = _validate_expense(form)
    if error:
        return _expense_form_response(request, form, error, status_code=400)
    create_expense(user["id"], **cleaned)
    return RedirectResponse(request.url_for("profile").path, status_code=303)


@app.get("/expenses/{id}/edit", response_class=HTMLResponse)
def edit_expense(request: Request, id: int):
    user = get_current_user(request)
    if not user:
        return _login_redirect(request)
    expense = get_expense(id, user["id"])
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    values = {
        "amount": _format_amount(expense["amount"]),
        "category": expense["category"],
        "date": expense["date"],
        "description": expense["description"] or "",
    }
    return _edit_form_response(request, id, values)


@app.post("/expenses/{id}/edit", response_class=HTMLResponse)
async def edit_expense_post(request: Request, id: int):
    user = get_current_user(request)
    if not user:
        return _login_redirect(request)
    if get_expense(id, user["id"]) is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    raw = (await request.body()).decode("utf-8", errors="replace")
    data = parse_qs(raw, keep_blank_values=True)
    form = {
        key: data.get(key, [""])[0]
        for key in ("amount", "category", "date", "description")
    }

    error, cleaned = _validate_expense(form)
    if error:
        return _edit_form_response(request, id, form, error, status_code=400)
    if not update_expense(id, user["id"], **cleaned):
        raise HTTPException(status_code=404, detail="Expense not found")
    return RedirectResponse(request.url_for("profile").path, status_code=303)


@app.get("/expenses/{id}/delete", response_class=PlainTextResponse)
def delete_expense(id: int):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8001)
