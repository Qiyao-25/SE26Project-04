# 对接说明 — PaperPipeline ↔ backend / UIPrototype

对齐对象（以当前仓库为准）：

- **backend** `POST /api/papers/batch`、`GET /api/papers/{id}/wiki`、`POST /api/papers/{id}/qa`
- **ORM** `entities.py`（`Paper` / `ParseTask` / `StructuredResult` / `TextChunk`）
- **UIPrototype** mock 字段（camelCase 引用卡片）

管线默认本地自给。设置 `PAPERMATE_API_BASE=http://127.0.0.1:8000` 后尝试真实入库，失败自动回退 `data/seed.json`。

## 已对齐（可联调）

| PaperPipeline | backend | 说明 |
|---------------|---------|------|
| `ingest.py` | `POST /api/papers/batch` | **请求体 = JSON 数组** `list[PaperUpsert]` |
| `paper_meta_to_backend` | `AuthorInput` | 作者字段为 `{name}`（非 `display_name`） |
| `wiki_to_backend_structured_rows` | `get_wiki()` | 写出 `summary` / `concepts` / `methods` / `limitations` 多行 |
| `QAResult.to_ui()` | `AskPaperResult` / mock | `pageNumber` / `sectionTitle` / `quote` |
| 信封解析 | `ApiResponse` | `{code, message, data, request_id}` |

### 批量入库示例

| 变量 | 默认 | 说明 |
|------|------|------|
| `PAPERMATE_API_BASE` | 空 | C FastAPI 根地址（如 `http://127.0.0.1:8000`） |
| `PAPERMATE_QA_MODE` | `sample` | `sample` 无 Key；`remote` 待 LLM |
| `PAPERMATE_SAMPLES_DIR` | `data/samples` | 本地样例 JSON |

## 成员 C（后端）— 当前与规划

| API | 状态 | PaperPipeline 用法 |
|-----|------|------------|
| `GET /health` | ✅ 已实现 | 联调探测 |
| `POST /api/papers/batch` | ✅ 已实现 | `crawler/ingest.py`（100 条元数据批量去重入库） |
| `GET /api/papers` | ✅ 已实现 | 数据库筛选、分页和详情 |
| `POST /api/search/chunks` | ✅ 已实现 | `integration/chunks_client.py` |
| `POST /api/papers/{paper_id}/parse` + `/api/tasks/{task_id}` | ✅ 已实现 | 解析任务状态与结构化结果入库 |
| `POST /qa` | ⬜ 待实现 | 可选；本地 QA 已可演示 |

### `POST /api/papers/batch` 请求体（PaperPipeline 已发送）

```json
{
  "papers": [{
    "arxiv_id": "1706.03762",
    "title": "Attention Is All You Need",
    "authors": [{"name": "Ashish Vaswani"}],
    "abstract": "...",
    "primary_category": "cs.CL",
    "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
    "source_url": "https://arxiv.org/abs/1706.03762",
    "ingest_status": "metadata_only",
    "authors": [{"display_name": "...", "author_order": 1}]
  }]
}
```

### `POST /api/search/chunks` 期望

```json
{ "arxiv_id": "1706.03762", "query": "...", "top_k": 5 }
```

成功响应 `data`: `{items, created, updated}`。

`src/pipeline/integration/backend_client.py` 提供了解析任务创建、结构化结果和文本块写入客户端；解析器可使用 `wiki_to_backend_structured()` 和 `chunk_to_backend()` 生成请求体。

## 成员 B（前端）— 消费约定

| 能力 | 状态 | 本地行为 |
|------|------|----------|
| `POST /api/search/chunks` | ❌ 无路由（表已有） | `ChunksClient` 搜 `data/samples` |
| `ParseTask` 入队/Worker | ❌ 仅 ORM | `MemoryTaskQueue` |
| 写入 `StructuredResult` / `TextChunk` | ❌ 无写 API | 产物在 samples / demo JSON；可用 `wiki_to_backend_structured_rows` / `paragraphs_to_text_chunks` 生成载荷 |
| DB QA 真实 RAG | ⚠️ 现为摘要 stub | PaperPipeline QA 做引用校验演示 |

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `PAPERMATE_API_BASE` | 空 | 如 `http://127.0.0.1:8000` |
| `PAPERMATE_QA_MODE` | `sample` | `remote` 待接 LLM |
| `PAPERMATE_SAMPLES_DIR` | `data/samples` | 本地分块 |

## 建议联调顺序

1. `GET /api/health`（已可用）
2. `POST /api/papers/batch` → 切换真实 ingest
3. 解析写入 `StructuredResult` 与 `TextChunk` → 关闭仅依赖 `paragraphs_preview`
4. `POST /api/search/chunks` → QA 远程检索
5. 前端 `qaService` / `paperService` 接真实 HTTP（字段已对齐 mock）
6. E 黄金题 + A ADR → contract V1
