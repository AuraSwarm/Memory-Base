# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] (2026-02-12)

### Added

- **Message.model**：`messages` 表新增可选列 `model`（VARCHAR 128），用于记录 assistant 回复使用的对话模型 ID；`init_db` 时执行 `ADD COLUMN IF NOT EXISTS`，兼容既有库。
- **init_db 迁移**：`employee_roles` 表可选列 `default_model`（VARCHAR 128），`init_db` 时执行 `ADD COLUMN IF NOT EXISTS`，兼容既有库。
- **OssStorage**: Aliyun OSS (Object Storage Service) backend using oss2 SDK. Optional dep `[oss]`. API ref: [阿里云 OSS API 概览](https://help.aliyun.com/zh/oss/developer-reference/list-of-operations-by-function).
- **create_long_term_backend_from_config(config)**: Factory to build long-term backend from app/aura config dict: OSS when `oss_endpoint`, `oss_bucket`, `oss_access_key_id`, `oss_access_key_secret` are set (endpoint normalized to `https://`); otherwise `InMemoryLongTermStorage`. Single backend per process; caller may cache.

## [0.1.0] - 2026-02-12

### Added

- **Database layer**: SQLAlchemy `Base`; models `Session`, `Message`, `SessionSummary`, `MessageArchive`, `AuditLog`; `SessionStatus` for archival; pgvector extension and `Message.embedding` (1536).
- **DB API**: `set_database_url`, `get_engine`, `get_session_factory`, `init_db`, `session_scope`, `log_audit`, `get_sync_engine`, `sync_session_scope`.
- **Long-term storage**: Protocol and backends for object storage (BOS / S3-compatible). `InMemoryLongTermStorage`, `S3CompatibleStorage`, `BosStorage`; `profile_key(user_id)`, `knowledge_key(user_id)`. Optional deps: `[s3]` (boto3), `[bos]` (baidubce).
- **Semantics**: User profile and knowledge triples format; `serialize_profile` / `parse_profile`, `serialize_triples` / `parse_triples`; `load_user_profile`, `save_user_profile`, `load_knowledge_triples`, `save_knowledge_triples`, `retrieve_relevant_knowledge` (keyword-based). `PROFILE_TRAIT_KEYS`.
- **Docs**: [记忆体系初稿-接入云端BOS.md](docs/记忆体系初稿-接入云端BOS.md); README with install, usage, and help; docstrings for public API.
- **Tests**: `test_base`, `test_db`, `test_models`, `test_long_term_storage`, `test_semantics` (35 tests).
- **Project**: `.gitattributes` (LF, text/binary); `.gitignore` (Python, Cursor, local, OS, temp, logs, other output paths); `hooks/` and `scripts/install-hooks.sh`.

[Unreleased]: https://github.com/your-org/Memory-Base/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/Memory-Base/releases/tag/v0.1.0
