# 记忆体系初稿：接入云端 BOS 长时存储

基于 [本地记忆体系](../.local/本地记忆体系.md) 与当前 Memory-Base / Agent-Backend 技术栈，本初稿定义**可接入云端 BOS（或 S3 兼容）的长时记忆体系**，在现有会话/消息/摘要/归档之上增加**用户级长期存储**与**推理时记忆注入**能力。

---

## 一、目标与范围

| 目标 | 说明 |
|------|------|
| 长时存储 | 用户画像、知识三元组等持久化到**对象存储（BOS / MinIO / S3）**，与 DB 热数据分离 |
| 与现有栈一致 | 复用 Memory-Base 的 Session/Message/SessionSummary、pgvector、归档模型；与 Agent-Backend 的 MinIO/归档任务可共存 |
| 可插拔后端 | 通过统一抽象接入百度 BOS 或 S3 兼容（MinIO/OSS），便于本地开发与云端部署 |

---

## 二、整体架构

```
记忆体系（初稿）
├── 1. 短期 / 会话层（已有）
│   └── Memory-Base: Session, Message, SessionSummary（PostgreSQL + pgvector）
├── 2. 中期 / 归档层（已有）
│   └── messages_archive、Celery 冷归档 / Parquet → MinIO
├── 3. 长期记忆层（本初稿）
│   ├── 对象存储后端（BOS / S3 兼容）
│   │   ├── profiles/{user_id}.json     — 用户画像
│   │   └── knowledge/{user_id}.jsonl   — 知识三元组
│   └── 索引（可选）：PostgreSQL knowledge_index（subject, predicate, object, embedding）
└── 4. 记忆注入（推理时）
    └── 从短期 + 中期摘要 + 长期（画像 + 知识）拼装增强 prompt
```

- **短期/中期**：沿用现有 Memory-Base + Agent-Backend 的 DB 与归档逻辑。  
- **长期**：仅新增「对象存储 + 可选 knowledge 索引」，不改变现有表的主键与分区策略。  
- **用户维度**：长期存储以 `user_id` 为粒度（与 本地记忆体系 一致）；Session 可携带 `user_id` 或由上层在写入/分析时映射。

---

## 三、长期存储内容与路径约定

| 类型 | 对象键 | 格式 | 说明 |
|------|--------|------|------|
| 用户画像 | `profiles/{user_id}.json` | JSON | communication_style, preferred_topics, decision_making 等 |
| 知识三元组 | `knowledge/{user_id}.jsonl` | JSONL | 每行一条 subject-predicate-object 或 JSON 行 |
| 元数据（可选） | `profiles/{user_id}.meta.json` | JSON | last_analyzed, version 等 |

- 所有键均置于同一 Bucket（如 `ai-memory-bucket` 或与现有 MinIO `archives` 分离的 `memory-long-term`）。  
- 若与 Agent-Backend 共用 MinIO，建议使用独立 Bucket 或前缀（如 `long_term/profiles/`）避免与 Parquet 归档混用。

---

## 四、对象存储抽象层

为支持 BOS 与 S3 兼容（MinIO/OSS）统一接入，在 Memory-Base 中增加**存储后端抽象**，推理与离线分析只依赖接口，不依赖具体云厂商。

### 4.1 抽象接口

```python
# memory_base.long_term_storage 概念接口

class LongTermStorageBackend(Protocol):
    def put_object(self, key: str, body: bytes | str, content_type: str | None = None) -> None: ...
    def get_object(self, key: str) -> bytes | None: ...
    def delete_object(self, key: str) -> None: ...
    def list_prefix(self, prefix: str) -> list[str]: ...  # 可选，用于列举 user 下的 key
```

- `key`：完整对象键，如 `profiles/u123.json`。  
- `body`：支持 `bytes` 或 `str`（内部统一为 bytes）。  
- 实现方负责 endpoint、认证、Bucket 等配置。

### 4.2 实现方式

| 后端 | 说明 | 依赖 |
|------|------|------|
| S3CompatibleStorage | MinIO / AWS S3 / 其他 S3 兼容 | boto3（optional） |
| BosStorage | 百度云 BOS | baidubce（optional） |

- 通过配置或环境变量选择后端类型及凭证；未配置时长期存储接口可降级为 no-op 或仅写本地文件，便于单机开发。

---

## 五、与现有数据模型的关系

- **Session / Message / SessionSummary**：不变；继续作为短期与中期数据源。  
- **MessageArchive**：不变；仍由现有 Celery 任务做冷归档。  
- **新增（可选）**：若需语义检索长期知识，可增加表 `knowledge_index`（user_id, subject, predicate, object, embedding vector），由离线分析任务在生成 `knowledge/{user_id}.jsonl` 时同步写入；检索时用 query embedding 在 PostgreSQL 中做近似最近邻。

与 本地记忆体系 的对应关系：

- `conversation_logs` → 当前用 Session + Message 表达，无需单独表。  
- `mid_term_memory` → 可用 SessionSummary 或后续扩展“用户维度”的 mid_term 表。  
- 长期层 → 本初稿的 BOS/S3 对象（profiles + knowledge） + 可选 knowledge_index。

---

## 六、核心流程（初稿）

### 6.1 写入长期记忆（离线/定时）

1. 按 `user_id` 聚合：从 Session/Message/SessionSummary（及可选 MessageArchive）拉取该用户近期数据。  
2. 抽象分析（与 本地记忆体系 一致）：  
   - 生成用户画像 → `profiles/{user_id}.json`  
   - 提取知识三元组 → `knowledge/{user_id}.jsonl`  
3. 调用 `LongTermStorageBackend.put_object` 写入对应 key。  
4. 若启用 knowledge_index，则同步写入 PostgreSQL 并更新 embedding。

### 6.2 推理时记忆注入

1. 短期：当前 Session 的最近 N 条 Message（或已有 context 压缩结果）。  
2. 中期：该用户最近数天的 SessionSummary 或摘要文本。  
3. 长期：  
   - `get_object("profiles/{user_id}.json")` → 解析为画像，拼进 system/prefix。  
   - 相关知识：从 `knowledge_index` 向量检索或直接读取 `knowledge/{user_id}.jsonl` 做简单过滤。  
4. 将上述三部分与当前 query 一起组装成 `get_enriched_prompt(...)` 的返回值，交给 LLM。

### 6.3 配置与安全

- BOS/S3 的 endpoint、bucket、access key 等通过配置或环境变量注入，不写死在代码中。  
- 若 BOS 支持服务端加密，建议在 Bucket 策略中开启；敏感字段可在写入前由应用层脱敏或过滤。

---

## 七、实施步骤建议

1. **实现并测试 `LongTermStorageBackend`**  
   - 在 Memory-Base 中实现 S3 兼容后端（MinIO），并加简单单测（如 put/get/delete）。  
   - 可选：实现 BOS 后端（baidubce），与同一接口对齐。

2. **定义并实现「长期记忆」读写 API**  
   - `save_user_profile(user_id, profile_dict)` → put `profiles/{user_id}.json`  
   - `load_user_profile(user_id)` → get 并解析 JSON  
   - `save_knowledge_triples(user_id, triples)` → 覆盖写入 `knowledge/{user_id}.jsonl`  
   - 上层再封装 `analyze_memory(user_id, days=7)` 与 `get_enriched_prompt(user_id, query)`。

3. **可选：PostgreSQL knowledge_index**  
   - 若需向量检索，增加表与 embedding 写入逻辑；否则可仅用 JSONL 做按需加载。

4. **与 Agent-Backend 集成**  
   - 在配置中增加 object_storage / long_term 段，或复用现有 MinIO 配置并区分 bucket/前缀。  
   - 在 chat 或 context 模块中调用 `get_enriched_prompt`，并在定时任务中调用 `analyze_memory`。

---

## 八、小结

本初稿在**不改变现有 Memory-Base/Agent-Backend 核心表结构**的前提下，通过**对象存储抽象 + 固定路径约定**，实现：

- 长期记忆写入 BOS 或 S3 兼容存储；  
- 推理时从短期、中期、长期三部分组装增强 prompt；  
- 后端可在 BOS 与 MinIO/S3 之间切换，便于本地开发与云端部署。

下一步可先落地 `memory_base.long_term_storage` 的接口与 S3 实现，再在应用层接 BOS 与 `analyze_memory` / `get_enriched_prompt`。

---

## 九、已实现模块（对应本初稿）

| 模块 | 说明 |
|------|------|
| `memory_base.long_term_storage` | 抽象接口 `LongTermStorageBackend`、路径辅助 `profile_key(user_id)` / `knowledge_key(user_id)` |
| `InMemoryLongTermStorage` | 内存后端，用于单测与本地无凭证开发 |
| `S3CompatibleStorage` | MinIO / AWS S3，需安装 `pip install memory-base[s3]` |
| `BosStorage` | 百度 BOS，需安装 `pip install memory-base[bos]` |
| `OssStorage` | 阿里云 OSS，需安装 `pip install memory-base[oss]`，[API 概览](https://help.aliyun.com/zh/oss/developer-reference/list-of-operations-by-function) |

使用示例：

```python
from memory_base import InMemoryLongTermStorage, profile_key, knowledge_key
import json

backend = InMemoryLongTermStorage()
backend.put_object(profile_key("u123"), json.dumps({"communication_style": "concise"}))
data = backend.get_object(profile_key("u123"))
# 接入 BOS：backend = BosStorage(bucket="ai-memory", access_key=..., secret_key=...)
# 接入 MinIO：backend = S3CompatibleStorage(bucket="memory-long-term", endpoint_url="http://localhost:9000", ...)
# 接入阿里云 OSS：backend = OssStorage(bucket="your-bucket", access_key_id=..., access_key_secret=..., endpoint="https://oss-cn-hangzhou.aliyuncs.com")
```
