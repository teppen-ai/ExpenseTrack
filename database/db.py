"""SQLite data layer for ExpenseTrack."""

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from pwdlib import PasswordHash

DB_PATH = Path(__file__).resolve().parent.parent / "expense_tracker.db"

CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)


def get_db():
    """Return a SQLite connection with dict-like rows and FK enforcement."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not exist. Safe to call repeatedly."""
    with closing(get_db()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                date        TEXT NOT NULL,
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )


def seed_db():
    """Insert the demo user and sample expenses once."""
    with closing(get_db()) as conn, conn:
        if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            return

        password_hash = PasswordHash.recommended().hash("demo123")
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@expensetrack.com", password_hash),
        )
        user_id = cursor.lastrowid

        today = date.today()
        samples = [
            (1, 12.50, "Food", "Lunch at cafe"),
            (3, 45.00, "Transport", "Monthly bus pass top-up"),
            (6, 120.00, "Bills", "Electricity bill"),
            (9, 30.00, "Health", "Pharmacy"),
            (12, 25.00, "Entertainment", "Movie tickets"),
            (16, 80.00, "Shopping", "New shoes"),
            (20, 15.00, "Other", None),
            (25, 60.00, "Food", "Weekly groceries"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, amount, category,
                 date(today.year, today.month, day).isoformat(), description)
                for day, amount, category, description in samples
            ],
        )


def get_user_by_email(email):
    """Return the user row for an email (case-insensitive), or None."""
    with closing(get_db()) as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()


def create_user(name, email, password):
    """Insert a new user with a hashed password and return the new id.

    Raises sqlite3.IntegrityError if the email is already registered.
    """
    password_hash = PasswordHash.recommended().hash(password)
    with closing(get_db()) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name.strip(), email.strip().lower(), password_hash),
        )
        return cursor.lastrowid
