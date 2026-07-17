# 对接说明 — PaperPipeline ↔ backend / UIPrototype

对齐对象（以当前仓库为准）：

- **backend** `POST /api/papers/batch`、任务队列、`finalize`、Wiki / chunks / QA
- **ORM** `Paper` / `ParseTask` / `StructuredResult` / `TextChunk`
- **UIPrototype** mock 字段（camelCase 引用卡片）

管线可本地自给（`data/seed.json` / samples）。设置 `PAPERMATE_API_BASE=http://127.0.0.1:8000` 后走真实入库与 Worker。

## 已对齐（可联调）

| PaperPipeline | backend | 说明 |
|---------------|---------|------|
| `ingest.py` / `BackendClient.batch_upsert_papers` | `POST /api/papers/batch` | **请求体 = JSON 数组** `list[PaperUpsert]`（服务端也接受 `{papers:[...]}`） |
| `paper_meta_to_backend` | `AuthorInput` | 作者字段为 `{name}` |
| `wiki_to_backend_structured_rows` | `GET .../wiki` | 写出 summary / concepts / methods / experiments / limitations |
| `chunk_to_backend` + `finalize` | `POST /api/tasks/{id}/finalize` | 原子提交 chunks + 结构化结果 |
| `QAResult.to_ui()` | `AskPaperResult` / mock | `pageNumber` / `sectionTitle` / `quote` |
| 信封解析 | `ApiResponse` | `{code, message, data, request_id}` |

## 成员 C（后端）— 联调 API

| API | 状态 | PaperPipeline 用法 |
|-----|------|--------------------|
| `GET /health` | ✅ | 联调探测 |
| `POST /api/papers/batch` | ✅ | `crawler/ingest.py`、联调脚本 |
| `GET /api/papers` | ✅ | 按 arxiv_id 回查 `paper_id` |
| `POST /api/papers/{id}/parse` | ✅ | 创建 `queued` 解析任务 |
| `GET/PATCH /api/tasks...` | ✅ | Worker 拉队列、改阶段 |
| `POST /api/tasks/{id}/finalize` | ✅ | `backend_worker` 写回结果 |
| `POST /api/papers/{id}/chunks` | ✅ | 亦可单独写 chunks |
| `GET /api/papers/{id}/wiki` | ✅ | 读结构化 Wiki |
| `POST /api/search/chunks` | ✅ | QA / 检索 |
| `POST /api/papers/{id}/qa` | ✅ | 基于 DB chunks 的问答 |

### `POST /api/papers/batch` 请求体（PaperPipeline 发送）

```json
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

成功 `data` 形如：`{items, created, updated}`。

### 建议联调顺序

1. 启动 backend：`uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. 一键联调（入库 → 创建任务 → Worker → Wiki/chunks）：

```powershell
cd SE26Project-04/PaperPipeline
$env:PYTHONPATH = "src"
$env:PAPERMATE_API_BASE = "http://127.0.0.1:8000"
python -m pipeline.run_se26_integration --arxiv-id 1706.03762
```

3. 批量入库：`python -m pipeline.crawler.run_crawl --target 20`
4. 常驻 Worker：`python -m pipeline.worker.run_backend_worker`
5. 前端接真实 HTTP（字段已对齐 mock）

产物：`data/integration/se26_last_run.json`

## 成员 B（前端）— 消费约定

| 能力 | PaperPipeline 侧 | 说明 |
|------|------------------|------|
| Wiki / 详情 | `GET /api/papers/{id}/wiki` | Worker finalize 后可读 |
| 引用检索 | `POST /api/search/chunks` | 无 API 时可回退 `data/samples` |
| QA 卡片 | `QAResult.to_ui()` | camelCase：`pageNumber` / `sectionTitle` / `quote` |

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `PAPERMATE_API_BASE` | 空 | 如 `http://127.0.0.1:8000` |
| `PAPERMATE_QA_MODE` | `sample` | `remote` 待接 LLM |
| `PAPERMATE_SAMPLES_DIR` | `data/samples` | 本地分块回退 |
