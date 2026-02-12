"""
Memory-Base: database and long-term storage for conversation memory.

Database (PostgreSQL + pgvector):
  Base, Session, Message, SessionSummary, MessageArchive, AuditLog, SessionStatus
  set_database_url, get_engine, get_session_factory, init_db, session_scope, log_audit
  get_sync_engine, sync_session_scope

Long-term storage (BOS / S3 / OSS):
  InMemoryLongTermStorage, S3CompatibleStorage, BosStorage, OssStorage
  profile_key, knowledge_key

Semantics (profiles and knowledge triples):
  serialize_profile, parse_profile, serialize_triples, parse_triples
  load_user_profile, save_user_profile, load_knowledge_triples, save_knowledge_triples
  retrieve_relevant_knowledge

See README.md and docs/记忆体系初稿-接入云端BOS.md. In Python: help(memory_base.retrieve_relevant_knowledge) etc.
"""

from memory_base.base import Base
from memory_base.db import (
    get_engine,
    get_session_factory,
    get_sync_engine,
    init_db,
    log_audit,
    session_scope,
    set_database_url,
    sync_session_scope,
)
from memory_base.long_term_storage import (
    BosStorage,
    InMemoryLongTermStorage,
    OssStorage,
    S3CompatibleStorage,
    create_long_term_backend_from_config,
    knowledge_key,
    profile_key,
)
from memory_base.models import Message, Session, SessionStatus, SessionSummary
from memory_base.models_archive import MessageArchive
from memory_base.models_audit import AuditLog
from memory_base.semantics import (
    load_knowledge_triples,
    load_user_profile,
    parse_profile,
    parse_triples,
    retrieve_relevant_knowledge,
    save_knowledge_triples,
    save_user_profile,
    serialize_profile,
    serialize_triples,
)

__all__ = [
    "Base",
    "Message",
    "MessageArchive",
    "Session",
    "SessionStatus",
    "SessionSummary",
    "AuditLog",
    "BosStorage",
    "InMemoryLongTermStorage",
    "OssStorage",
    "S3CompatibleStorage",
    "create_long_term_backend_from_config",
    "get_engine",
    "get_session_factory",
    "get_sync_engine",
    "init_db",
    "knowledge_key",
    "load_knowledge_triples",
    "load_user_profile",
    "log_audit",
    "parse_profile",
    "parse_triples",
    "profile_key",
    "retrieve_relevant_knowledge",
    "save_knowledge_triples",
    "save_user_profile",
    "serialize_profile",
    "serialize_triples",
    "session_scope",
    "set_database_url",
    "sync_session_scope",
]
