# PaperPipeline — 论文处理流水线（成员 D）

对应项目交付：**arXiv 抓取 → PDF 解析 → 结构化 Wiki → 出处问答**。  
对齐当前 `backend`（`/api/papers/*`）与 `UIPrototype` mock。

- 字段契约：[INTEGRATION.md](./INTEGRATION.md)
- 职责与集成：[ROLE_AND_INTEGRATION.md](./ROLE_AND_INTEGRATION.md)（与 `ppp/成员D_职责与集成方案.md` 同内容）

> 原名 `PartD` / `Arxiv` 已更名为 **PaperPipeline**。

## 目录

```text
PaperPipeline/
├── README.md / INTEGRATION.md / ROLE_AND_INTEGRATION.md
├── scripts/spike_one_paper.py
├── src/pipeline/          # crawler · parser · summarizer · qa · worker · integration
├── data/ · test/pipeline/ · docs/spike/ · model/analysis/pipeline/
```

## 环境与运行

```powershell
cd SE26Project-04/PaperPipeline
pip install -r requirements.txt
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"

python -m pipeline.worker.run_demo
python -m pipeline.worker.run_backend_worker --once
python -m pipeline.qa.run_eval
```

联调入库（backend 需已启动）：

```powershell
$env:PAPERMATE_API_BASE = "http://127.0.0.1:8000"
python -m pipeline.crawler.run_crawl --target 20
```

| 目标 | 命令 |
|------|------|
| Spike | `python scripts/spike_one_paper.py pipeline --arxiv-id 1706.03762` |
| 抓取 ≥100 | `python -m pipeline.crawler.run_crawl --target 100` |
| 解析 10 篇 | `python -m pipeline.parser.run_samples` |
| QA 20 题 | `python -m pipeline.qa.run_eval` |
| 三篇演示 | `python test/pipeline/run_full_demo.py` |

### 数据库解析 Worker

前端创建解析任务后，需要启动数据库 Worker 消费 `queued` 任务。Worker 会下载 PDF、使用 `pypdf` 提取带页码的段落、生成结构化摘要，并写回 C 后端：

```powershell
cd SE26Project-04/PaperPipeline
$env:PYTHONPATH = "src"
$env:PAPERMATE_API_BASE = "http://127.0.0.1:8000"
python -m pipeline.worker.run_backend_worker
```

只处理一个任务可使用 `--once`；限制处理数量可使用 `--max-tasks N`，常驻运行时可用 `--poll-interval`、`--stale-timeout` 和 `--recover-interval` 控制轮询与卡住任务恢复。PDF 默认缓存到 `data/worker_pdfs`，HTML 默认缓存到 `data/worker_html`，可分别通过 `--pdf-dir`、`--html-dir` 修改。默认 PDF 优先、解析失败后回退 ar5iv；验证 HTML 路径时可添加 `--prefer-html`。Worker 运行环境需要先执行 `pip install -r requirements.txt`。

Worker 支持可选的 OpenAI-compatible 解析 Agent。设置 `PAPERMATE_AGENT_ENABLED=true`、`PAPERMATE_AGENT_API_KEY`、`PAPERMATE_AGENT_MODEL` 和 `PAPERMATE_AGENT_BASE_URL` 后，结构化摘要会由 Agent 生成；未配置或调用失败时继续使用规则抽取降级。

## 交付对应（迭代 2）

| 成果 | 路径 |
|------|------|
| seed ≥100 | `data/seed.json` |
| 解析评分 | `data/samples/scorecard.json` |
| QA 评测 | `test/pipeline/qa_results.json` |
| 全链路演示 | `data/demo/` |
