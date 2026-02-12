# Memory-Base

Abstracted database layer for conversation memory: sessions, messages, session summaries, audit log, and archive. Built for PostgreSQL with pgvector (async via asyncpg, sync via psycopg2). Optional long-term storage (BOS / S3-compatible) for user profiles and knowledge triples, with abstract semantics and semantic retrieval.

## Contents

- **Base**: SQLAlchemy `DeclarativeBase` for all models.
- **Models**: `Session`, `Message`, `SessionSummary`, `MessageArchive`, `AuditLog`; `SessionStatus` constants for archival.
- **DB API**:
  - `set_database_url(url)` – set default URL (e.g. at app startup).
  - `get_engine()`, `get_session_factory()` – async engine/session factory (use default URL).
  - `init_db()` – create pgvector extension and all tables.
  - `session_scope()` – async context manager for a session (commit/rollback).
  - `log_audit(session, action, resource_type, ...)` – write audit log row.
  - `get_sync_engine()`, `sync_session_scope()` – for Celery/background tasks.
- **Long-term storage** (optional): `InMemoryLongTermStorage`, `S3CompatibleStorage`, `BosStorage`; `profile_key(user_id)`, `knowledge_key(user_id)`. See [记忆体系初稿](docs/记忆体系初稿-接入云端BOS.md).
- **Semantics**: `serialize_profile` / `parse_profile`, `serialize_triples` / `parse_triples`; `load_user_profile`, `save_user_profile`, `load_knowledge_triples`, `save_knowledge_triples`, `retrieve_relevant_knowledge`.

## Install

```bash
pip install -e .
```

Requires: `sqlalchemy[asyncio]`, `asyncpg`, `psycopg2-binary`, `pgvector`.

Optional backends:

```bash
pip install -e ".[s3]"    # MinIO / AWS S3 (boto3)
pip install -e ".[bos]"   # Baidu BOS (baidubce)
pip install -e ".[dev]"   # pytest for tests
```

## Usage

### Database (sessions, messages, summaries)

Application (e.g. Agent-Backend) sets the default URL at startup, then uses the same Base for app-specific tables so `init_db()` creates all tables:

```python
from memory_base import set_database_url, init_db, get_session_factory, session_scope, Session, Message

# At startup
set_database_url("postgresql+asyncpg://user:pass@localhost/db")
await init_db()

# In request handlers
async with session_scope() as session:
    session.add(Session(title="Chat"))
    await session.flush()
```

For sync (e.g. Celery), pass the URL explicitly:

```python
from memory_base.db import sync_session_scope

with sync_session_scope(database_url) as db:
    ...
```

### Long-term storage (profiles, knowledge triples)

Use an in-memory backend for tests or local dev; use `S3CompatibleStorage` or `BosStorage` for production (install `.[s3]` or `.[bos]`):

```python
from memory_base import InMemoryLongTermStorage, save_user_profile, load_user_profile, save_knowledge_triples, retrieve_relevant_knowledge

backend = InMemoryLongTermStorage()
save_user_profile(backend, "u1", {"user_id": "u1", "traits": {"communication_style": "concise"}})
profile = load_user_profile(backend, "u1")

save_knowledge_triples(backend, "u1", [("用户", "使用", "BOS"), ("用户", "部署", "AI服务")])
triples = retrieve_relevant_knowledge(backend, "u1", "BOS", top_k=5)
```

With MinIO (S3-compatible):

```python
from memory_base import S3CompatibleStorage

backend = S3CompatibleStorage(
    bucket="memory-long-term",
    endpoint_url="http://localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
)
```

With Baidu BOS:

```python
from memory_base import BosStorage

backend = BosStorage(bucket="ai-memory", access_key="...", secret_key="...", endpoint="https://bj.bcebos.com")
```

## Documentation and help

- Design doc (long-term memory, BOS): [docs/记忆体系初稿-接入云端BOS.md](docs/记忆体系初稿-接入云端BOS.md).
- In Python, use `help()` on the package or any public function:

```python
import memory_base
help(memory_base)                      # package overview and __all__
help(memory_base.retrieve_relevant_knowledge)
help(memory_base.S3CompatibleStorage)
help(memory_base.session_scope)
```

## Testing

Module tests: `pytest tests/` (install with `pip install -e ".[dev]"`). Overall/integration tests are run from **Aura-Swarm**.

```bash
pytest tests/ -v
```

## Agent-Backend

Agent-Backend uses Memory-Base for all shared storage; it keeps app-specific models (e.g. `CodeReview`) in its own package, using `memory_base.Base` so they are created by `init_db()`. Local dev: install this repo in editable mode, then install Agent-Backend (`pip install -e ../Memory-Base && pip install -e .`).
