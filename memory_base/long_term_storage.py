"""
Long-term memory storage backend: abstract interface and implementations.

- LongTermStorageBackend: protocol for put/get/delete/list.
- S3CompatibleStorage: MinIO / AWS S3 / any S3-compatible (optional boto3).
- BosStorage: Baidu BOS (optional baidubce).

Object key convention (see docs/记忆体系初稿-接入云端BOS.md):
  profiles/{user_id}.json
  knowledge/{user_id}.jsonl
"""

from __future__ import annotations

from typing import Protocol


def profile_key(user_id: str) -> str:
    """Return object storage key for user profile (e.g. profiles/u123.json)."""
    return f"profiles/{user_id}.json"


def knowledge_key(user_id: str) -> str:
    """Return object storage key for user knowledge triples (e.g. knowledge/u123.jsonl)."""
    return f"knowledge/{user_id}.jsonl"


class LongTermStorageBackend(Protocol):
    """Protocol for long-term object storage (BOS, S3, MinIO)."""

    def put_object(self, key: str, body: bytes | str, content_type: str | None = None) -> None:
        """Upload object. key is full path (e.g. profiles/u123.json)."""
        ...

    def get_object(self, key: str) -> bytes | None:
        """Download object; return None if not found."""
        ...

    def delete_object(self, key: str) -> None:
        """Delete object by key."""
        ...

    def list_prefix(self, prefix: str) -> list[str]:
        """List object keys under prefix (e.g. profiles/)."""
        ...


class InMemoryLongTermStorage:
    """
    In-memory backend for tests and local dev without cloud credentials.

    Implements put_object, get_object, delete_object, list_prefix; no external services.
    """

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def put_object(self, key: str, body: bytes | str, content_type: str | None = None) -> None:
        self._store[key] = body.encode("utf-8") if isinstance(body, str) else body

    def get_object(self, key: str) -> bytes | None:
        return self._store.get(key)

    def delete_object(self, key: str) -> None:
        self._store.pop(key, None)

    def list_prefix(self, prefix: str) -> list[str]:
        return [k for k in self._store if k.startswith(prefix)]


class S3CompatibleStorage:
    """
    S3-compatible backend (MinIO, AWS S3, etc.).

    Requires: pip install boto3 (or pip install -e ".[s3]").
    """

    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None = None,
        region_name: str = "us-east-1",
        access_key: str | None = None,
        secret_key: str | None = None,
    ):
        """
        Args:
            bucket: Bucket name.
            endpoint_url: Optional endpoint (e.g. http://localhost:9000 for MinIO).
            region_name: AWS region when using AWS S3.
            access_key: Access key (optional if using env/instance profile).
            secret_key: Secret key (optional if using env/instance profile).
        """
        self.bucket = bucket
        self._endpoint_url = endpoint_url
        self._region_name = region_name
        self._access_key = access_key
        self._secret_key = secret_key
        self._client = None

    def _get_client(self):
        import boto3
        from botocore.config import Config

        if self._client is None:
            kwargs = {
                "service_name": "s3",
                "region_name": self._region_name,
                "config": Config(signature_version="s3v4"),
            }
            if self._endpoint_url:
                kwargs["endpoint_url"] = self._endpoint_url
            if self._access_key and self._secret_key:
                kwargs["aws_access_key_id"] = self._access_key
                kwargs["aws_secret_access_key"] = self._secret_key
            self._client = boto3.client(**kwargs)
        return self._client

    def put_object(self, key: str, body: bytes | str, content_type: str | None = None) -> None:
        client = self._get_client()
        payload = body.encode("utf-8") if isinstance(body, str) else body
        extra = {}
        if content_type:
            extra["ContentType"] = content_type
        client.put_object(Bucket=self.bucket, Key=key, Body=payload, **extra)

    def get_object(self, key: str) -> bytes | None:
        client = self._get_client()
        from botocore.exceptions import ClientError

        try:
            resp = client.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                return None
            raise

    def delete_object(self, key: str) -> None:
        client = self._get_client()
        client.delete_object(Bucket=self.bucket, Key=key)

    def list_prefix(self, prefix: str) -> list[str]:
        client = self._get_client()
        paginator = client.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents") or []:
                keys.append(obj["Key"])
        return keys


class BosStorage:
    """
    Baidu BOS backend.

    Requires: pip install baidubce (or pip install -e ".[bos]").
    """

    def __init__(
        self,
        bucket: str,
        access_key: str,
        secret_key: str,
        endpoint: str = "https://bj.bcebos.com",
    ):
        """
        Args:
            bucket: BOS bucket name.
            access_key: BOS access key.
            secret_key: BOS secret key.
            endpoint: BOS endpoint (e.g. https://bj.bcebos.com).
        """
        self.bucket = bucket
        self._access_key = access_key
        self._secret_key = secret_key
        self._endpoint = endpoint.rstrip("/")
        self._client = None

    def _get_client(self):
        from baidubce.bce_client_configuration import BceClientConfiguration
        from baidubce.auth.bce_credentials import BceCredentials
        from baidubce.services.bos.bos_client import BosClient

        if self._client is None:
            config = BceClientConfiguration(
                credentials=BceCredentials(self._access_key, self._secret_key),
                endpoint=self._endpoint,
            )
            self._client = BosClient(config)
        return self._client

    def put_object(self, key: str, body: bytes | str, content_type: str | None = None) -> None:
        client = self._get_client()
        if isinstance(body, str):
            content = body
            client.put_object_from_string(
                bucket_name=self.bucket,
                key=key,
                data=content,
            )
        else:
            # bytes: use put_object_from_data if available, else encode to string
            if hasattr(client, "put_object_from_data"):
                client.put_object_from_data(
                    bucket_name=self.bucket,
                    key=key,
                    data=body,
                    content_type=content_type or "application/octet-stream",
                )
            else:
                client.put_object_from_string(
                    bucket_name=self.bucket,
                    key=key,
                    data=body.decode("utf-8"),
                )

    def get_object(self, key: str) -> bytes | None:
        client = self._get_client()
        from baidubce.exception import BceError

        try:
            if hasattr(client, "get_object_as_bytes"):
                return client.get_object_as_bytes(bucket_name=self.bucket, key=key)
            resp = client.get_object(bucket_name=self.bucket, key=key)
            return resp.body.read()
        except BceError as e:
            if getattr(e, "status_code", None) == 404:
                return None
            raise

    def delete_object(self, key: str) -> None:
        client = self._get_client()
        client.delete_object(bucket_name=self.bucket, key=key)

    def list_prefix(self, prefix: str) -> list[str]:
        client = self._get_client()
        keys = []
        marker = None
        while True:
            resp = client.list_objects(
                bucket_name=self.bucket,
                prefix=prefix,
                marker=marker,
                max_keys=1000,
            )
            for obj in resp.body.contents:
                keys.append(obj.key)
            if not resp.body.is_truncated:
                break
            marker = resp.body.next_marker
        return keys
