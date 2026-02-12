"""Tests for long-term storage backends and key helpers."""

import json

import pytest

from memory_base.long_term_storage import (
    InMemoryLongTermStorage,
    knowledge_key,
    profile_key,
)


def test_profile_key() -> None:
    assert profile_key("u123") == "profiles/u123.json"
    assert profile_key("user-456") == "profiles/user-456.json"


def test_knowledge_key() -> None:
    assert knowledge_key("u123") == "knowledge/u123.jsonl"
    assert knowledge_key("user-456") == "knowledge/user-456.jsonl"


def test_in_memory_put_get() -> None:
    backend = InMemoryLongTermStorage()
    backend.put_object("profiles/u1.json", '{"name": "test"}')
    out = backend.get_object("profiles/u1.json")
    assert out is not None
    assert json.loads(out.decode("utf-8")) == {"name": "test"}


def test_in_memory_put_bytes() -> None:
    backend = InMemoryLongTermStorage()
    backend.put_object("k", b"binary")
    assert backend.get_object("k") == b"binary"


def test_in_memory_get_missing() -> None:
    backend = InMemoryLongTermStorage()
    assert backend.get_object("missing") is None


def test_in_memory_delete() -> None:
    backend = InMemoryLongTermStorage()
    backend.put_object("k", "v")
    backend.delete_object("k")
    assert backend.get_object("k") is None


def test_in_memory_list_prefix() -> None:
    backend = InMemoryLongTermStorage()
    backend.put_object("profiles/u1.json", "{}")
    backend.put_object("profiles/u2.json", "{}")
    backend.put_object("knowledge/u1.jsonl", "")
    keys = backend.list_prefix("profiles/")
    assert set(keys) == {"profiles/u1.json", "profiles/u2.json"}
