import pytest
from fastapi.testclient import TestClient

from database import db


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    return db.DB_PATH


@pytest.fixture
def client(temp_db):
    from app import app  # imported after DB_PATH is patched

    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client
