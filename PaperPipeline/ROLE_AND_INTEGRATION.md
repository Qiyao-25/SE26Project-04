# 成员 D 工作职责与项目集成方案

| 项 | 内容 |
|----|------|
| 角色 | 成员 D · 算法与数据管线 |
| 交付目录 | `SE26Project-04/PaperPipeline/`（本地副本：`ppp/PaperPipeline/`） |
| 对齐后端 | `SE26Project-04/backend/`（已含 `/api/papers/*`） |
| 对齐前端 | `SE26Project-04/UIPrototype/` |

---

## 1. 成员 D 工作的具体作用

一句话：**把「外部论文」变成系统可检索、可展示、可带出处问答的内部数据与算法能力。**

在整条产品链中，D 解决的是 **内容从哪来、怎么变成结构化知识、如何保证问答不瞎编**；C 负责存与 API；B 负责呈现。

```text
arXiv 原文
    │
    ▼
┌──────────────────────────────────────┐
│ PaperPipeline（成员 D）               │
│  抓取 → 解析 → Wiki三件套 → 出处问答  │
│  幂等任务队列 · 失败拒答 · 本地降级   │
└───────────────┬──────────────────────┘
                │ 元数据 / 结构化结果 / 分块（契约）
                ▼
┌──────────────────────────────────────┐
│ backend（成员 C）                     │
│  持久化 · /api/papers · 统一信封      │
└───────────────┬──────────────────────┘
                │ HTTP JSON
                ▼
┌──────────────────────────────────────┐
│ UIPrototype（成员 B）                 │
│  列表 / 详情 / Wiki / 引用卡片        │
└──────────────────────────────────────┘
```

### 1.1 对应项目成果（迭代目标）

| 项目交付物 | 成员 D 贡献 |
|------------|-------------|
| arXiv 抓取 + 去重 Demo | `crawler/` → `data/seed.json`（≥100） |
| PDF 全文解析 Demo | `parser/` → `data/samples/`（≥8/10） |
| 自动化处理流水线 | `worker/` 状态机 + 幂等/重试 |
| 结构化摘要/概念/方法 | `summarizer/` → 对齐 backend wiki 的 `StructuredResult` 行 |
| 原文出处绑定问答 | `qa/`：检索 + `chunk_id` 校验 + 拒答 |

### 1.2 对用户可见价值

| 用户用例 | 没有 D 时 | 有 D 时 |
|----------|-----------|---------|
| 手动抓取 / 订阅更新 | 只能看 mock 6 篇 | 可持续从 arXiv 拉元数据并入库 |
| 查看 AI 总结 / Wiki | 仅 mock 或 abstract 占位 | 真实解析出的 summary/concepts/methods |
| 智能问答 | 摘要拼答案、引用弱 | 段落级检索 + 页码/章节引用；无证据拒答 |
| 管理员任务看板 | 无真实任务态 | 任务阶段、失败码、耗时日志（本地已具备） |

### 1.3 当前边界（不做什么）

- **不**做前端页面与路由（B）
- **不**做 FastAPI 路由与数据库 migration（C）
- **不**做账号权限（可后续协同）
- 默认 **不依赖 LLM Key**（样例模式保证可演示）

---

## 2. 相对新版 backend 的修正要点

backend 已从「仅 health」升级为 **双通道 papers API**（DB 数字 ID + mock 字符串 ID）。PaperPipeline 已做如下修正：

| 问题 | 修正 |
|------|------|
| 路径 `/papers/batch` | → **`POST /api/papers/batch`** |
| 请求体 `{"papers":[...]}` | → **JSON 数组** `list[PaperUpsert]` |
| 作者 `display_name` | → **`{name}`**（`AuthorInput`） |
| Wiki 单块 `wiki_triple` | → **`summary` / `concepts` / `methods` / `limitations` 多行**（`wiki_to_backend_structured_rows`） |
| 分块检索 API 不存在 | → 远程 best-effort + **本地 samples 兜底**；文档标明待 C 补 `POST /api/search/chunks` |

代码位置：`PaperPipeline/src/pipeline/integration/contracts.py`、`crawler/ingest.py`、`INTEGRATION.md`。

---

## 3. 集成到项目中的方案

### 3.1 目标架构（推荐）

```text
[Browser] → UIPrototype
               │  VITE_USE_MOCK=false
               ▼
          backend :8000
               │  POST /api/papers/batch（已通）
               │  未来：写 StructuredResult / TextChunk
               │  未来：POST /api/search/chunks · 真 RAG QA
               ▼
          PaperPipeline Worker（独立进程或定时任务）
               │  读 arXiv / 解析 PDF
               ▼
          SQLite/PostgreSQL（同一 PAPERMATE_DATABASE_URL）
```

原则：**C 拥有写库权威；D 产出算法结果并通过契约写入（或由 C 提供写入 API 供 D 调用）。**

### 3.2 分阶段落地（建议 4 步）

#### 阶段 A — 元数据闭环（可立即做）

1. 启动 backend：`uvicorn app.main:app --port 8000`
2. PaperPipeline：
   ```powershell
   cd SE26Project-04/PaperPipeline
   $env:PYTHONPATH="src"
   $env:PAPERMATE_API_BASE="http://127.0.0.1:8000"
   python -m pipeline.crawler.run_crawl --target 20
   ```
3. 验证：`GET /api/papers?keyword=attention` 能看到入库论文  
4. UI：对 **数字 paper_id** 走 DB 详情（mock 字符串 ID 仍演示固定 6 篇）

**验收：** 抓取成功 → DB 有记录；API 宕机时仍有 `seed.json`。

#### 阶段 B — Wiki 内容闭环（需 C 小接口）

成员 C 增加其一即可：

- `POST /api/papers/{paper_id}/structured` 接收 `wiki_to_backend_structured_rows()` 的 rows；或  
- Worker 同进程直接写 ORM（若 D/C 合仓部署）

同时更新 `Paper.ingest_status = "parsed"`，使 `parse_status=completed`。

**验收：** `GET /api/papers/{id}/wiki` 返回非空 concepts/methods（不再只有 abstract）。

#### 阶段 C — 出处问答闭环（需 C 分块检索）

1. D 解析后调用写入 `TextChunk`（`paragraphs_to_text_chunks`）
2. C 提供 `POST /api/search/chunks`（或内部服务）
3. 将 `POST /api/papers/{id}/qa` 从「摘要 stub」改为：调检索 → 生成/模板回答 → 返回 UI 形 citations
4. 可选：QA 逻辑直接复用 `pipeline.qa.service.QAService`（作为库被 backend 调用）

**验收：** 问答引用含 `pageNumber`/`quote`；P9/P10 类不可用拒答。

#### 阶段 D — 任务可观测（管理后台）

1. C 暴露 `ParseTask` 创建/查询 API  
2. D Worker 写 `ParseTask` 状态（queued→running→succeeded/failed）  
3. UI 管理端「任务队列」读 DB，不再纯 mock

### 3.3 代码集成两种部署方式

| 方式 | 做法 | 适用 |
|------|------|------|
| **A. 进程分离（推荐）** | D 独立跑 crawl/worker；经 HTTP 调 C | 课程演示、职责清晰 |
| **B. 库内嵌** | backend `service` import `pipeline.qa` / `parser` | 单机演示、减少 HTTP |

近期建议 **A**：已有 `PAPERMATE_API_BASE` 与本地回退，改动最小。

### 3.4 协作检查清单

| 成员 | 待办 |
|------|------|
| **D** | 保持契约与 backend 同步；提供 rows/chunks 载荷；本地评测 20 题 |
| **C** | batch 已完成；补 structured/chunks 写与搜；QA 换真检索 |
| **B** | `VITE_USE_MOCK=false` 接数字 ID；引用卡片字段已对齐 mock |
| **A/E** | ADR 冻结字段；黄金题替换 `data/qa/questions.json` |

---

## 4. 快速命令索引

```powershell
# 仅本地（不依赖 backend）
cd SE26Project-04/PaperPipeline
$env:PYTHONPATH="src"
python -m pipeline.worker.run_demo
python -m pipeline.qa.run_eval

# 联调入库
$env:PAPERMATE_API_BASE="http://127.0.0.1:8000"
python -m pipeline.crawler.run_crawl --target 20
```

更细的字段表见：`SE26Project-04/PaperPipeline/INTEGRATION.md`。
