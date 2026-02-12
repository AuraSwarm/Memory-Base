"""Module tests: memory_base.db (URL handling, no real DB connection)."""

from memory_base.db import set_database_url, get_engine, get_sync_engine


def test_set_database_url_and_get_engine():
    set_database_url("postgresql+asyncpg://postgres:postgres@localhost:5432/test_mb")
    engine = get_engine()
    assert engine is not None
    assert hasattr(engine, "connect")


def test_get_sync_engine_returns_engine():
    set_database_url("postgresql+asyncpg://postgres:postgres@localhost:5432/test_mb")
    engine = get_sync_engine()
    assert engine is not None
    assert hasattr(engine, "connect")
