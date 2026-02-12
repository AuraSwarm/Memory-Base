"""
Abstract semantics and semantic retrieval for long-term memory.

- User profile: JSON schema (traits.communication_style, preferred_topics, etc.).
- Knowledge triples: (subject, predicate, object) stored as JSONL.
- load/save profile and triples via any LongTermStorageBackend.
- retrieve_relevant_knowledge: load triples and return those matching query (keyword match;
  vector-based retrieval is left to the application layer with pgvector).
"""

from __future__ import annotations

import json
from typing import Protocol

from memory_base.long_term_storage import knowledge_key, profile_key


class _StorageProtocol(Protocol):
    """Minimal protocol for semantics load/save (avoids circular import)."""

    def get_object(self, key: str) -> bytes | None: ...
    def put_object(self, key: str, body: bytes | str, content_type: str | None = None) -> None: ...

# Profile traits keys from 本地记忆体系 (abstract semantics). Use when building or validating profile["traits"].
PROFILE_TRAIT_KEYS = (
    "communication_style",
    "emotional_tone",
    "preferred_topics",
    "decision_making",
)


def serialize_profile(profile: dict) -> bytes:
    """Encode user profile dict to JSON bytes (ensure_ascii=False for Chinese)."""
    return json.dumps(profile, ensure_ascii=False).encode("utf-8")


def parse_profile(raw: bytes) -> dict:
    """Decode JSON bytes to user profile dict. Raises json.JSONDecodeError on invalid input."""
    return json.loads(raw.decode("utf-8"))


def serialize_triples(triples: list[tuple[str, str, str]]) -> bytes:
    """Encode list of (subject, predicate, object) to JSONL: one JSON array per line."""
    lines = [json.dumps([s, p, o], ensure_ascii=False) for s, p, o in triples]
    return "\n".join(lines).encode("utf-8")


def parse_triples(raw: bytes) -> list[tuple[str, str, str]]:
    """Decode JSONL to list of (subject, predicate, object). Empty lines skipped."""
    result = []
    for line in raw.decode("utf-8").strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        arr = json.loads(line)
        if isinstance(arr, list) and len(arr) >= 3:
            result.append((str(arr[0]), str(arr[1]), str(arr[2])))
    return result


def load_user_profile(backend: _StorageProtocol, user_id: str) -> dict | None:
    """
    Load user profile from storage.

    Args:
        backend: Storage backend (e.g. InMemoryLongTermStorage, S3CompatibleStorage).
        user_id: User identifier.

    Returns:
        Profile dict, or None if key does not exist.
    """
    key = profile_key(user_id)
    data = backend.get_object(key)
    if data is None:
        return None
    return parse_profile(data)


def save_user_profile(
    backend: _StorageProtocol,
    user_id: str,
    profile: dict,
) -> None:
    """Save user profile to storage (JSON). Overwrites existing key."""
    key = profile_key(user_id)
    backend.put_object(key, serialize_profile(profile), content_type="application/json")


def load_knowledge_triples(
    backend: _StorageProtocol,
    user_id: str,
) -> list[tuple[str, str, str]]:
    """
    Load knowledge triples from storage.

    Args:
        backend: Storage backend.
        user_id: User identifier.

    Returns:
        List of (subject, predicate, object); empty if key does not exist.
    """
    key = knowledge_key(user_id)
    data = backend.get_object(key)
    if data is None:
        return []
    return parse_triples(data)


def save_knowledge_triples(
    backend: _StorageProtocol,
    user_id: str,
    triples: list[tuple[str, str, str]],
) -> None:
    """Save knowledge triples to storage (JSONL). Overwrites existing key."""
    key = knowledge_key(user_id)
    backend.put_object(key, serialize_triples(triples), content_type="application/x-ndjson")


def retrieve_relevant_knowledge(
    backend: _StorageProtocol,
    user_id: str,
    query: str,
    top_k: int = 5,
) -> list[tuple[str, str, str]]:
    """
    Semantic retrieval: load triples and return those relevant to query.

    Base implementation uses keyword match (query substring in subject/predicate/object).
    For vector similarity, use embedding + pgvector in the application layer.

    Args:
        backend: Storage backend.
        user_id: User identifier.
        query: Search query (matched as substring, case-insensitive).
        top_k: Maximum number of triples to return.

    Returns:
        List of (subject, predicate, object) matching the query, up to top_k.
        If query is empty, returns first top_k triples.
    """
    triples = load_knowledge_triples(backend, user_id)
    if not query.strip():
        return triples[:top_k]
    q = query.strip().lower()
    matched = []
    for t in triples:
        if q in (t[0] + " " + t[1] + " " + t[2]).lower():
            matched.append(t)
    return matched[:top_k]
