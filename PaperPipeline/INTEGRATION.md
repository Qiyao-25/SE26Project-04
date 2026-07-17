# 对接说明 — 成员 D 管线

对齐对象：
- **backend** `app/model/entities.py`（ORM）+ `ApiResponse{code,message,data,request_id}`
- **UIPrototype** `frontend/src/mocks/paper-*.json`（前端展示字段）

管线默认本地自给。设置 `PAPERMATE_API_BASE` 后尝试调用成员 C API，失败自动回退。

## 字段对照（易错点）

| 管线 / ORM | UIPrototype mock | 说明 |
|------------|------------------|------|
| `arxiv_id` | `arxivId` / `paperId` | 前端用 camelCase |
| `primary_category` | `primaryCategory` | 入库勿再传 `categories[]` |
| `source_url` | `sourceUrl` | 勿用 `abs_url` |
| `page_no` | `pageNumber` | QA 引用卡片 |
| `section` | `sectionTitle` | QA 引用卡片 |
| `content` / `quote` | `quote` | 引用原文片段 |
| `chunk_id` | （前端暂不展示） | 保留供校验；UI 用 `citationId` |
| `content_json.{summary,concept,methods}` | `summary` + `concepts[]` + `methods[]` | Wiki 摘要页 |
| ParseTask `queued/running/succeeded/failed` | `parseStatus`: pending/parsing/completed/failed | 状态粗粒度映射 |

适配实现：`src/pipeline/integration/contracts.py`

## 环境变量

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
    "title": "...",
    "abstract": "...",
    "published_at": null,
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

响应接受 `ApiResponse.data.chunks[]`，字段：`chunk_id`, `page_no`, `section`, `content`, `score`。

`src/pipeline/integration/backend_client.py` 提供了解析任务创建、结构化结果和文本块写入客户端；解析器可使用 `wiki_to_backend_structured()` 和 `chunk_to_backend()` 生成请求体。

## 成员 B（前端）— 消费约定

PaperPipeline 可输出 UI 兼容形状（无需改前端 mock 字段名）：

```python
from pipeline.qa.service import QAService
result = QAService().ask("1706.03762", "Multi-Head Attention 的作用？")
ui_payload = result.to_ui(paper_id="attention", paper_title="Attention Is All You Need")
# ui_payload.citations[].pageNumber / sectionTitle / quote
```

Wiki 摘要：`wiki_to_ui_summary(...)` → 对齐 `paper-summary.json`。

## 成员 A / E

- **A**：ADR 冻结后更新 `schemas.py` + `contracts.py`
- **E**：替换 `data/qa/questions.json` 后执行 `python -m pipeline.qa.run_eval`

## 建议联调顺序

1. `GET /api/health`（已可用）
2. `POST /api/papers/batch` → 切换真实 ingest
3. 解析写入 `StructuredResult` 与 `TextChunk` → 关闭仅依赖 `paragraphs_preview`
4. `POST /api/search/chunks` → QA 远程检索
5. 前端 `qaService` / `paperService` 接真实 HTTP（字段已对齐 mock）
6. E 黄金题 + A ADR → contract V1
