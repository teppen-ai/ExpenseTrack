from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse(request, "landing.html")


@app.get("/register", response_class=HTMLResponse)
def register(request: Request):
    return templates.TemplateResponse(request, "register.html")


@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse(request, "login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.get("/logout", response_class=PlainTextResponse)
def logout():
    return "Logout — coming in Step 3"


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

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
