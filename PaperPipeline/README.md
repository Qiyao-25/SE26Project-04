# PaperPipeline — 论文处理流水线（成员 D）

对应项目交付：**arXiv 抓取 → PDF 解析 → 结构化 Wiki → 出处问答**。
对齐 `backend` ORM 与 `UIPrototype` mock 契约。

> 原名 `PartD` / `Arxiv` 已按功能更名为 **PaperPipeline**（与 `backend`、`UIPrototype` 并列）。

## 目录

```text
PaperPipeline/
├── README.md / INTEGRATION.md / requirements.txt
├── scripts/spike_one_paper.py
├── src/pipeline/          # crawler · parser · summarizer · qa · worker · integration
├── data/                  # seed、samples、qa、demo、spike
├── test/pipeline/
├── docs/spike/
└── model/analysis/pipeline/
```

## 环境与运行

```powershell
cd SE26Project-04/PaperPipeline
pip install -r requirements.txt
$env:PYTHONPATH = "src"
$env:PYTHONIOENCODING = "utf-8"

python -m pipeline.worker.run_demo
python -m pipeline.qa.run_eval
python test/pipeline/run_full_demo.py
```

| 目标 | 命令 |
|------|------|
| Spike 单篇 | `python scripts/spike_one_paper.py pipeline --arxiv-id 1706.03762` |
| 抓取 ≥100 | `python -m pipeline.crawler.run_crawl --target 100` |
| 解析 10 篇 | `python -m pipeline.parser.run_samples` |
| QA 20 题 | `python -m pipeline.qa.run_eval` |
| 稳定性 | `python -m pipeline.worker.run_stability` |
| 性能 / 三篇演示 | `python test/pipeline/run_benchmark.py` |

可选：`$env:PAPERMATE_API_BASE = "http://127.0.0.1:8000"`（失败自动本地回退）。

## 交付对应（迭代 2）

| 项目成果 | 本目录证据 |
|----------|------------|
| arXiv 抓取+去重 Demo | `data/seed.json`（≥100） |
| PDF 解析 Demo | `data/samples/scorecard.json`（≥8/10） |
| 自动化处理流水线 | `src/pipeline/worker/` |
| 结构化 summary/concept/methods | `summarizer/` + samples JSON |
| 原文出处绑定问答 | `qa/` + `test/pipeline/qa_results.json` |

对接细节见 [INTEGRATION.md](./INTEGRATION.md)。提交步骤见 [COMMIT.md](./COMMIT.md)。
