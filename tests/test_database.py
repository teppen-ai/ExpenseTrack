import re
import sqlite3
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash

from database import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    return db.DB_PATH


def _query(sql, params=()):
    conn = db.get_db()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_init_db_creates_tables_and_is_idempotent(temp_db):
    db.init_db()
    db.init_db()
    names = {r["name"] for r in _query(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"users", "expenses"} <= names


def test_get_db_row_factory_and_foreign_keys(temp_db):
    conn = db.get_db()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("SELECT 1 AS one").fetchone()["one"] == 1
    finally:
        conn.close()


def test_seed_inserts_once(temp_db):
    db.init_db()
    db.seed_db()
    db.seed_db()
    assert _query("SELECT COUNT(*) AS c FROM users")[0]["c"] == 1
    assert _query("SELECT COUNT(*) AS c FROM expenses")[0]["c"] == 8


def test_seed_password_is_hashed(temp_db):
    db.init_db()
    db.seed_db()
    stored = _query("SELECT password_hash FROM users")[0]["password_hash"]
    assert stored != "demo123"
    assert PasswordHash.recommended().verify("demo123", stored)


def test_seed_categories_and_dates(temp_db):
    db.init_db()
    db.seed_db()
    rows = _query("SELECT category, date FROM expenses")
    assert {r["category"] for r in rows} == set(db.CATEGORIES)
    prefix = date.today().strftime("%Y-%m")
    for r in rows:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"])
        assert r["date"].startswith(prefix)


def test_duplicate_email_rejected(temp_db):
    db.init_db()
    db.seed_db()
    conn = db.get_db()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO users (name, email, password_hash) "
                "VALUES (?, ?, ?)",
                ("Other", "demo@expensetrack.com", "x"),
            )
    finally:
        conn.close()


def test_invalid_user_id_rejected(temp_db):
    db.init_db()
    conn = db.get_db()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date) "
                "VALUES (?, ?, ?, ?)",
                (999, 1.0, "Food", "2026-01-01"),
            )
    finally:
        conn.close()


def test_app_startup_initialises_db(temp_db):
    from app import app

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
    assert temp_db.exists()
    assert _query("SELECT COUNT(*) AS c FROM expenses")[0]["c"] == 8
