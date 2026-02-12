"""Tests for abstract semantics (profile/triples format) and semantic retrieval."""

import json

from memory_base.long_term_storage import InMemoryLongTermStorage
from memory_base.semantics import (
    PROFILE_TRAIT_KEYS,
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


# ---- 抽象语义：用户画像 ----
def test_serialize_parse_profile_roundtrip() -> None:
    profile = {
        "user_id": "u1",
        "traits": {
            "communication_style": "concise",
            "emotional_tone": "neutral",
            "preferred_topics": ["AI", "cloud"],
            "decision_making": "data-driven",
        },
        "last_updated": "2026-02-12",
    }
    raw = serialize_profile(profile)
    assert isinstance(raw, bytes)
    back = parse_profile(raw)
    assert back == profile


def test_profile_ensure_ascii_false() -> None:
    profile = {"traits": {"communication_style": "简洁"}, "user_id": "u1"}
    raw = serialize_profile(profile)
    assert "简洁" in raw.decode("utf-8")
    back = parse_profile(raw)
    assert back["traits"]["communication_style"] == "简洁"


def test_profile_trait_keys_defined() -> None:
    """抽象语义：画像应包含约定 trait 键（可选但约定一致）"""
    assert "communication_style" in PROFILE_TRAIT_KEYS
    assert "preferred_topics" in PROFILE_TRAIT_KEYS
    assert "decision_making" in PROFILE_TRAIT_KEYS


def test_parse_profile_empty_object() -> None:
    back = parse_profile(b"{}")
    assert back == {}


# ---- 抽象语义：知识三元组 ----
def test_serialize_parse_triples_roundtrip() -> None:
    triples = [
        ("用户", "使用", "BOS"),
        ("用户", "部署", "AI服务"),
    ]
    raw = serialize_triples(triples)
    assert isinstance(raw, bytes)
    back = parse_triples(raw)
    assert back == triples


def test_triples_jsonl_one_per_line() -> None:
    triples = [("s", "p", "o")]
    raw = serialize_triples(triples)
    line = raw.decode("utf-8").strip()
    arr = json.loads(line)
    assert arr == ["s", "p", "o"]


def test_parse_triples_skips_empty_lines() -> None:
    raw = b'["a","b","c"]\n\n["d","e","f"]'
    back = parse_triples(raw)
    assert back == [("a", "b", "c"), ("d", "e", "f")]


def test_parse_triples_empty_returns_empty() -> None:
    assert parse_triples(b"") == []
    assert parse_triples(b"\n\n") == []


def test_triples_three_tuple_semantics() -> None:
    """抽象语义：三元组为 (subject, predicate, object) 三个字符串"""
    triples = [("主体", "谓语", "客体")]
    raw = serialize_triples(triples)
    back = parse_triples(raw)
    assert len(back) == 1
    assert len(back[0]) == 3
    assert back[0][0] == "主体" and back[0][1] == "谓语" and back[0][2] == "客体"


# ---- 语义获取：通过存储 load/save ----
def test_save_load_user_profile_via_backend() -> None:
    backend = InMemoryLongTermStorage()
    profile = {"user_id": "u1", "traits": {"communication_style": "detailed"}}
    save_user_profile(backend, "u1", profile)
    loaded = load_user_profile(backend, "u1")
    assert loaded is not None
    assert loaded["user_id"] == "u1"
    assert loaded["traits"]["communication_style"] == "detailed"


def test_load_user_profile_missing_returns_none() -> None:
    backend = InMemoryLongTermStorage()
    assert load_user_profile(backend, "nonexistent") is None


def test_save_load_knowledge_triples_via_backend() -> None:
    backend = InMemoryLongTermStorage()
    triples = [
        ("用户", "使用", "BOS"),
        ("用户", "部署", "AI服务"),
    ]
    save_knowledge_triples(backend, "u1", triples)
    loaded = load_knowledge_triples(backend, "u1")
    assert loaded == triples


def test_load_knowledge_triples_missing_returns_empty() -> None:
    backend = InMemoryLongTermStorage()
    assert load_knowledge_triples(backend, "nonexistent") == []


# ---- 语义获取：retrieve_relevant_knowledge ----
def test_retrieve_relevant_knowledge_keyword_match() -> None:
    backend = InMemoryLongTermStorage()
    triples = [
        ("用户", "使用", "BOS"),
        ("用户", "部署", "AI服务"),
        ("项目", "使用", "PostgreSQL"),
    ]
    save_knowledge_triples(backend, "u1", triples)
    # 语义获取：查询包含 "BOS" 应返回含 BOS 的三元组
    out = retrieve_relevant_knowledge(backend, "u1", "BOS", top_k=5)
    assert len(out) == 1
    assert out[0] == ("用户", "使用", "BOS")


def test_retrieve_relevant_knowledge_multiple_matches_top_k() -> None:
    backend = InMemoryLongTermStorage()
    triples = [
        ("用户", "使用", "BOS"),
        ("用户", "使用", "MinIO"),
        ("用户", "使用", "S3"),
    ]
    save_knowledge_triples(backend, "u1", triples)
    out = retrieve_relevant_knowledge(backend, "u1", "使用", top_k=2)
    assert len(out) == 2
    assert all("使用" in (t[0] + t[1] + t[2]) for t in out)


def test_retrieve_relevant_knowledge_empty_query_returns_prefix() -> None:
    backend = InMemoryLongTermStorage()
    triples = [("a", "b", "c"), ("d", "e", "f")]
    save_knowledge_triples(backend, "u1", triples)
    out = retrieve_relevant_knowledge(backend, "u1", "", top_k=1)
    assert len(out) == 1


def test_retrieve_relevant_knowledge_no_match_returns_empty() -> None:
    backend = InMemoryLongTermStorage()
    save_knowledge_triples(backend, "u1", [("用户", "使用", "BOS")])
    out = retrieve_relevant_knowledge(backend, "u1", "不存在的关键词", top_k=5)
    assert out == []


def test_retrieve_relevant_knowledge_no_triples_stored_returns_empty() -> None:
    backend = InMemoryLongTermStorage()
    out = retrieve_relevant_knowledge(backend, "u1", "任意", top_k=5)
    assert out == []
