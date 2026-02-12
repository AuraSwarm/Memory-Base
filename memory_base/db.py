"""
Database engine, async/sync session factory, and audit logging.

- Async engine and session for PostgreSQL (asyncpg).
- Optional default database_url via set_database_url() so callers can use get_engine()/get_session_factory() without passing URL.
- log_audit() for key operations (tool calls, config reload, etc.).
- get_sync_engine() for Celery/background tasks using psycopg2.
"""

import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from uuid import UUID

from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine as create_sync_engine

from memory_base.base import Base
from memory_base import models  # noqa: F401 - register Session, Message, SessionSummary with Base.metadata
from memory_base import models_archive  # noqa: F401 - register MessageArchive with Base.metadata
from memory_base import models_audit  # noqa: F401 - register AuditLog with Base.metadata
from memory_base.models_audit import AuditLog

# Lazy init; default URL can be set by application at startup
_default_url: str | None = None
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_sync_engine = None


def set_database_url(database_url: str) -> None:
    """Set the default database URL for get_engine() and get_session_factory()."""
    global _default_url
    _default_url = database_url


def get_engine(database_url: str | None = None):
    """
    Create or return async engine; ensure pgvector extension exists.
    Uses default URL from set_database_url() if database_url is not provided.
    """
    global _engine
    url = database_url or _default_url
    if url is None:
        raise RuntimeError("database_url not set: call set_database_url() or pass database_url= to get_engine()")
    if _engine is None:
        _engine = create_async_engine(
            url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_sync_engine(database_url: str | None = None):
    """
    Create or return sync engine (postgresql:// with psycopg2) for Celery/background tasks.
    Converts postgresql+asyncpg:// to postgresql:// if needed.
    """
    global _sync_engine
    url = database_url or _default_url
    if url is None:
        raise RuntimeError("database_url not set: call set_database_url() or pass database_url= to get_sync_engine()")
    sync_url = url.replace("postgresql+asyncpg", "postgresql")
    if _sync_engine is None:
        _sync_engine = create_sync_engine(sync_url, pool_pre_ping=True)
    return _sync_engine


async def init_db(engine=None, database_url: str | None = None) -> None:
    """
    Create pgvector extension and tables (for init / tests).
    If engine is provided, use it; otherwise create from database_url or default URL.
    """
    if engine is None:
        engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session_factory(database_url: str | None = None) -> async_sessionmaker[AsyncSession]:
    """Return async session factory. Uses default URL from set_database_url() if not provided."""
    global _session_factory
    url = database_url or _default_url
    if url is None:
        raise RuntimeError("database_url not set: call set_database_url() or pass database_url= to get_session_factory()")
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(url),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def session_scope(database_url: str | None = None) -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for a single DB session (commit on success, rollback on error)."""
    factory = get_session_factory(database_url)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def sync_session_scope(database_url: str | None = None):
    """Sync context manager for a single DB session (e.g. Celery). Use: with sync_session_scope() as db: ..."""
    from contextlib import contextmanager

    @contextmanager
    def _scope():
        engine = get_sync_engine(database_url)
        Session = sessionmaker(engine, expire_on_commit=False)
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _scope()


async def log_audit(
    session: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: str | UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Write an audit log entry (e.g. tool call, config reload, denied CLI).
    Caller is responsible for committing the session.
    """
    await session.execute(
        insert(AuditLog.__table__).values(
            id=uuid.uuid4(),
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
        )
    )
