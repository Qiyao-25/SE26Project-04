# 对接说明 — PaperPipeline ↔ backend / UIPrototype

当前主线默认由 backend 的 FastAPI 进程在点击解析后直接执行解析任务；PaperPipeline 的独立 Worker 仍保留用于兼容旧部署和批量补偿，不再是页面解析的前置条件。

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
|-----|------|------------|
| `GET /health` | ✅ 已实现 | 联调探测 |
| `POST /api/papers/batch` | ✅ 已实现 | `crawler/ingest.py`（100 条元数据批量去重入库） |
| `GET /api/papers` | ✅ 已实现 | 数据库筛选、分页和详情 |
| `POST /api/search/chunks` | ✅ 已实现 | `integration/chunks_client.py` |
| `POST /api/papers/{paper_id}/parse` + `/api/tasks/{task_id}` | ✅ 已实现 | 解析任务状态与结构化结果入库 |
| `POST /api/tasks/{task_id}/retry` / `recover-stale` | ✅ 已实现 | 失败重试与卡住任务恢复 |
| `POST /api/tasks/enqueue-pending` | ✅ 已实现 | 将 metadata-only 论文批量加入解析队列 |
| `POST /api/tasks/{task_id}/finalize` / `GET /api/tasks/stats` | ✅ 已实现 | 解析结果原子提交与队列观测 |
| 可选解析/QA Agent | ✅ 适配层已实现 | OpenAI-compatible；无 Key 自动降级 |
| `POST /api/papers/{paper_id}/qa` | ✅ 已实现 | 数据库文本块 QA；无证据时拒答 |

### `POST /api/papers/batch` 请求体（PaperPipeline 已发送）

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
