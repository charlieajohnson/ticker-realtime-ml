"""Shared test fixtures — temp DuckDB, test app client."""

import os
import tempfile

import pytest

# Point settings at a temp database before any backend imports
_tmp = tempfile.mkdtemp()
os.environ["DUCKDB_PATH"] = os.path.join(_tmp, "test.db")

from backend.config import get_settings, Settings  # noqa: E402
from backend.database import init_tables, get_connection, reset_connection  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    """Give each test its own temp DuckDB file."""
    # Close any existing singleton connection before switching DB path
    reset_connection()

    db_file = str(tmp_path / "test.db")

    # Clear lru_cache so settings reload
    get_settings.cache_clear()
    monkeypatch.setenv("DUCKDB_PATH", db_file)

    init_tables()
    yield
    reset_connection()
    get_settings.cache_clear()


@pytest.fixture
def db():
    """Return the singleton DuckDB connection."""
    return get_connection()
