"""Tests for long-term storage backends and key helpers."""

import json
import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

from memory_base.long_term_storage import (
    InMemoryLongTermStorage,
    OssStorage,
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


def test_oss_storage_has_protocol_methods() -> None:
    """OssStorage implements LongTermStorageBackend (no oss2 required for this check)."""
    backend = OssStorage(
        bucket="b",
        access_key_id="ak",
        access_key_secret="sk",
        endpoint="https://oss-cn-hangzhou.aliyuncs.com",
    )
    assert hasattr(backend, "put_object") and callable(backend.put_object)
    assert hasattr(backend, "get_object") and callable(backend.get_object)
    assert hasattr(backend, "delete_object") and callable(backend.delete_object)
    assert hasattr(backend, "list_prefix") and callable(backend.list_prefix)


def _make_oss_mock_bucket():
    """Build mock oss2 module and bucket for OssStorage tests (no real Aliyun credentials)."""
    mock_bucket = MagicMock()
    mock_oss2 = MagicMock()
    mock_oss2.Auth.return_value = None
    mock_oss2.Bucket.return_value = mock_bucket
    mock_oss2.exceptions.NoSuchKey = type("NoSuchKey", (Exception,), {})
    return mock_oss2, mock_bucket


def test_oss_storage_put_object() -> None:
    """OssStorage.put_object calls bucket.put_object with key, body, and optional Content-Type."""
    mock_oss2, mock_bucket = _make_oss_mock_bucket()
    mock_oss2.ObjectIterator.return_value = iter([])
    with patch.dict("sys.modules", {"oss2": mock_oss2}):
        backend = OssStorage(
            bucket="test-bucket",
            access_key_id="ak",
            access_key_secret="sk",
            endpoint="https://oss-cn-hangzhou.aliyuncs.com",
        )
        backend.put_object("profiles/u1.json", '{"a":1}', content_type="application/json")
    mock_bucket.put_object.assert_called_once()
    call_kw = mock_bucket.put_object.call_args
    assert call_kw[0][0] == "profiles/u1.json"
    assert call_kw[0][1] == b'{"a":1}'
    assert call_kw[1]["headers"] == {"Content-Type": "application/json"}


def test_oss_storage_put_object_bytes() -> None:
    """OssStorage.put_object sends bytes as-is."""
    mock_oss2, mock_bucket = _make_oss_mock_bucket()
    with patch.dict("sys.modules", {"oss2": mock_oss2}):
        backend = OssStorage("b", "ak", "sk", "https://oss-cn-hangzhou.aliyuncs.com")
        backend.put_object("k", b"binary")
    mock_bucket.put_object.assert_called_once_with("k", b"binary", headers={})


def test_oss_storage_get_object_found() -> None:
    """OssStorage.get_object returns body when key exists."""
    mock_oss2, mock_bucket = _make_oss_mock_bucket()
    mock_result = MagicMock()
    mock_result.read.return_value = b'{"traits":{}}'
    mock_bucket.get_object.return_value = mock_result
    with patch.dict("sys.modules", {"oss2": mock_oss2}):
        backend = OssStorage("b", "ak", "sk", "https://oss-cn-hangzhou.aliyuncs.com")
        out = backend.get_object("profiles/u1.json")
    assert out == b'{"traits":{}}'
    mock_bucket.get_object.assert_called_once_with("profiles/u1.json")


def test_oss_storage_get_object_not_found() -> None:
    """OssStorage.get_object returns None when key does not exist (NoSuchKey)."""
    mock_oss2, mock_bucket = _make_oss_mock_bucket()
    mock_bucket.get_object.side_effect = mock_oss2.exceptions.NoSuchKey()
    with patch.dict("sys.modules", {"oss2": mock_oss2}):
        backend = OssStorage("b", "ak", "sk", "https://oss-cn-hangzhou.aliyuncs.com")
        out = backend.get_object("missing.json")
    assert out is None


def test_oss_storage_delete_object() -> None:
    """OssStorage.delete_object calls bucket.delete_object."""
    mock_oss2, mock_bucket = _make_oss_mock_bucket()
    with patch.dict("sys.modules", {"oss2": mock_oss2}):
        backend = OssStorage("b", "ak", "sk", "https://oss-cn-hangzhou.aliyuncs.com")
        backend.delete_object("profiles/u1.json")
    mock_bucket.delete_object.assert_called_once_with("profiles/u1.json")


def test_oss_storage_list_prefix() -> None:
    """OssStorage.list_prefix returns object keys under prefix (excludes directory placeholders)."""
    mock_oss2, mock_bucket = _make_oss_mock_bucket()
    obj1 = MagicMock()
    obj1.key = "profiles/u1.json"
    obj1.is_prefix.return_value = False
    obj2 = MagicMock()
    obj2.key = "profiles/u2.json"
    obj2.is_prefix.return_value = False
    prefix_placeholder = MagicMock()
    prefix_placeholder.key = "profiles/"
    prefix_placeholder.is_prefix.return_value = True
    mock_oss2.ObjectIterator.return_value = iter([obj1, prefix_placeholder, obj2])
    with patch.dict("sys.modules", {"oss2": mock_oss2}):
        backend = OssStorage("b", "ak", "sk", "https://oss-cn-hangzhou.aliyuncs.com")
        keys = backend.list_prefix("profiles/")
    assert keys == ["profiles/u1.json", "profiles/u2.json"]
    mock_oss2.ObjectIterator.assert_called_once_with(mock_bucket, prefix="profiles/")


def _get_real_oss_config():
    """Read OSS config from env; return (endpoint, access_key_id, access_key_secret, bucket) or None if missing."""
    endpoint = os.environ.get("ALIYUN_OSS_ENDPOINT") or os.environ.get("OSS_ENDPOINT")
    access_key_id = os.environ.get("ALIYUN_OSS_ACCESS_KEY_ID") or os.environ.get("OSS_ACCESS_KEY_ID")
    access_key_secret = os.environ.get("ALIYUN_OSS_ACCESS_KEY_SECRET") or os.environ.get("OSS_ACCESS_KEY_SECRET")
    bucket = os.environ.get("ALIYUN_OSS_BUCKET") or os.environ.get("OSS_BUCKET")
    if not all([endpoint, access_key_id, access_key_secret, bucket]):
        return None
    return (endpoint.strip("/"), access_key_id, access_key_secret, bucket)


@pytest.mark.real_oss
def test_oss_storage_real_api_put_get_list_delete() -> None:
    """Real Aliyun OSS API: put_object -> get_object -> list_prefix -> delete_object (requires oss2 + env credentials)."""
    try:
        import oss2  # noqa: F401
    except ImportError:
        pytest.skip("oss2 not installed; pip install oss2 or pip install -e '.[oss]'")

    cfg = _get_real_oss_config()
    if cfg is None:
        pytest.skip(
            "Real OSS credentials not set. Set ALIYUN_OSS_ACCESS_KEY_ID, ALIYUN_OSS_ACCESS_KEY_SECRET, "
            "ALIYUN_OSS_ENDPOINT (e.g. https://oss-cn-hangzhou.aliyuncs.com), ALIYUN_OSS_BUCKET"
        )

    endpoint, access_key_id, access_key_secret, bucket = cfg
    backend = OssStorage(
        bucket=bucket,
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        endpoint=endpoint,
    )

    prefix = f"memory_base_test/{uuid.uuid4().hex}/"
    key1 = prefix + "profiles/test_user.json"
    key2 = prefix + "knowledge/test_user.jsonl"
    body1 = '{"traits": {"test": true}}'
    body2 = "triple1\ntriple2\n"

    backend.put_object(key1, body1, content_type="application/json")
    backend.put_object(key2, body2)

    out1 = backend.get_object(key1)
    assert out1 is not None
    assert out1.decode("utf-8") == body1
    out2 = backend.get_object(key2)
    assert out2 is not None
    assert out2.decode("utf-8") == body2

    keys = backend.list_prefix(prefix)
    assert set(keys) == {key1, key2}

    backend.delete_object(key1)
    backend.delete_object(key2)
    assert backend.get_object(key1) is None
    assert backend.get_object(key2) is None
    assert backend.list_prefix(prefix) == []
