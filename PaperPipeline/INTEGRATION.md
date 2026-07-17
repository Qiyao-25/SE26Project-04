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

```http
POST /api/papers/batch
Content-Type: application/json

[
  {
    "arxiv_id": "1706.03762",
    "title": "Attention Is All You Need",
    "authors": [{"name": "Ashish Vaswani"}],
    "abstract": "...",
    "primary_category": "cs.CL",
    "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
    "source_url": "https://arxiv.org/abs/1706.03762",
    "ingest_status": "metadata_only"
  }
]
```

成功响应 `data`: `{items, created, updated}`。

## 尚未由 backend 提供（PaperPipeline 本地兜底）

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

1. `GET /health`
2. `python -m pipeline.crawler.run_crawl` + `PAPERMATE_API_BASE` → 验证 batch 入库
3. 成员 C：增加「解析结果写入」API（StructuredResult + TextChunk + 更新 `ingest_status=parsed`）
4. 成员 C：`POST /api/search/chunks` → PaperPipeline QA 切远程检索
5. 替换 backend QA stub 为基于 chunks 的检索；UI 关掉 mock

详见 `ppp/成员D_职责与集成方案.md`。
