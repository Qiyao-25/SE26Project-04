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

## 交付证据

| 成果 | 路径 |
|------|------|
| seed ≥100 | `data/seed.json` |
| 解析评分 | `data/samples/scorecard.json` |
| QA 评测 | `test/pipeline/qa_results.json` |
| 全链路演示 | `data/demo/` |
