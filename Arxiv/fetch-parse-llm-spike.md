# 抓取 / 解析 / 摘要 Spike 结果记录（H017–H018）

| 项 | 内容 |
|----|------|
| 任务 | **H017**（上午）+ **H018**（下午） |
| 日期 | 2026-07-15（**2026-07-16 按 backend ORM 修订**） |
| 负责人 | 成员 D |
| 脚本 | `Arxiv/scripts/spike_one_paper.py` |
| 依赖 | `pypdf`（见 `requirements-spike.txt`） |
| Backend | `SE26Project-04/backend/app/model/entities.py`（H015/H016 骨架） |
| 样例 | **P1** `1706.03762`（Attention Is All You Need） |
| 同步 | 自 `ppp/TechPrototype` · 2026-07-16 backend 对齐 |

---

## 0. 与 backend 对齐（本次修订）

Spike **仍独立跑 arXiv**（不调用 FastAPI）；输出增加 `backend_paper` / `backend_upsert`，字段对齐 ORM。

| Spike 字段 | Backend ORM |
|------------|-------------|
| `paper.arxiv_id`（去版本后缀） | `Paper.arxiv_id` |
| `title` / `abstract` / `categories[0]` | `Paper.title` / `abstract` / `primary_category` |
| `pdf_url` / abs | `Paper.pdf_url` / `source_url` |
| `authors[]` | `Author` + `PaperAuthor.author_order` |
| `pdf_path` | `PaperContent.storage_path` |
| `structured.{summary,concept,methods}` | `StructuredResult.content_json`（`result_type=wiki_triple`） |
| 管线 run | `ParseTask`（`full_pipeline` + `idempotency_key`） |

**当前 backend 仅** `GET /health`；入库路由待 C（H045+）。

---

## 1. 可复现命令

在 `SE26Project-04/Arxiv/`：

```powershell
pip install -r requirements-spike.txt
$env:PYTHONIOENCODING='utf-8'
python scripts/spike_one_paper.py fetch --keyword "attention is all you need"
python scripts/spike_one_paper.py pipeline --arxiv-id 1706.03762
```

| 类型 | 路径 |
|------|------|
| H017 | `data/h017_fetch.json` |
| H018 | `data/h018_pipeline.json` |
| 归档 | `data/runs/run_*.json`（含 `run_20260716T030426Z.json`） |

---

## 2. H017 结果

| 项 | 值 |
|----|-----|
| 关键词 | `attention is all you need` |
| 耗时 | **1.62s** |
| 状态 | `ok` |
| Spike 字段 | arxiv_id、title、authors、abstract、categories、pdf_url、abs_url |
| Backend 映射 | 输出含 `backend_paper`（`ingest_status=metadata_only` 等） |

> 关键词首条可能非 P1；H018 用冻结 ID `1706.03762`。

---

## 3. H018 结果（P1）

| 阶段 | 耗时 | 状态 |
|------|------|------|
| fetch_metadata | 2.12s | ok |
| download_pdf | 28.40s | ok |
| parse_pdf | 2.17s | ok |
| summarize | &lt;0.01s | ok |
| **端到端** | **~32.7s** | `summarized` → 映射 `ParseTask.status=succeeded` |

三件套非空 → `StructuredResult.content_json`。产物含 `backend_upsert`。

### 已知限制

| # | 现象 | 后续 |
|---|------|------|
| 1 | 抽取式摘要非 LLM | H067 接生成 |
| 2 | ID 可能带 `v7` | 映射时规范为 base id |
| 3 | 未调 backend API | C 提供入库路由后接 `PAPERMATE_API_BASE` |

---

## 4. 跑分（P1）

| SpikeID | 耗时 | 状态 | Pass |
|---------|------|------|------|
| S1-P1 | 30.5s | fetched | Pass |
| S2-P1 | 2.17s | parsed | Pass |
| S3-P1 | &lt;0.01s | summarized | Pass |

---

## 5. 验收

| 任务 | 结论 |
|------|------|
| H017 | **通过**（含 backend_paper 映射） |
| H018 | **通过**（含 backend_upsert 映射） |

## 6. 下游

- H027/H028 UML：**V1.1** 已按 ORM 命名（`ParseTask` / `TextChunk.page_no`）
- H048：seed 降级 → 待 `POST /papers/batch` 或 worker upsert
