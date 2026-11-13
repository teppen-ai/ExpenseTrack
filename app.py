import sqlite3
from contextlib import asynccontextmanager
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from auth import clear_session_cookie, get_current_user, set_session_cookie
from database.db import (  # noqa: F401
    create_user,
    get_db,
    get_user_by_email,
    init_db,
    seed_db,
    verify_user,
)

MIN_PASSWORD_LENGTH = 8


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_db()
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(
    directory="templates",
    context_processors=[
        lambda request: {"current_user": get_current_user(request)}
    ],
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
    response = RedirectResponse(request.url_for("landing").path, status_code=303)
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


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.get("/profile", response_class=PlainTextResponse)
def profile():
    return "Profile page — coming in Step 4"


@app.get("/expenses/add", response_class=PlainTextResponse)
def add_expense():
    return "Add expense — coming in Step 7"


@app.get("/expenses/{id}/edit", response_class=PlainTextResponse)
def edit_expense(id: int):
    return "Edit expense — coming in Step 8"


@app.get("/expenses/{id}/delete", response_class=PlainTextResponse)
def delete_expense(id: int):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8001)
