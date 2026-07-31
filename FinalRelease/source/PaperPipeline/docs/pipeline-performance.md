# PaperMate 管线性能报告（H087/H088）

> 生成方式：`python test/pipeline/run_benchmark.py` + `python test/pipeline/run_full_demo.py`  
> 模式：**无 Key 样例模式**（本地检索 + 规则摘要，不调用付费 LLM）

## 1. 测试环境

| 项 | 值 |
|----|-----|
| 日期 | 2026-07-16 |
| 样例 | P1 `1706.03762`、P2 `1810.04805`、P7 `2005.11401` |
| 阶段 | fetch → parse → summarize → qa |
| 数据 | `data/samples/` 本地 PDF + 缓存 JSON |

## 2. 阶段耗时（单篇，实测）

| 样例 | fetch | parse | summarize | qa | 合计 |
|------|-------|-------|-----------|-----|------|
| P1 `1706.03762` | 0.050s | 0.062s | 0.030s | 0.003s | **0.145s** |
| P2 `1810.04805` | 0.059s | 0.062s | 0.031s | 0.002s | **0.154s** |
| P7 `2005.11401` | 0.060s | 0.062s | 0.031s | 0.002s | **0.155s** |
| **均值** | 0.056s | 0.062s | 0.031s | 0.002s | **0.151s** |

数据来源：`test/pipeline/benchmark.json`（2026-07-16 实测）

### Spike 超时对照

| 阶段 | Spike 上限 | 说明 |
|------|------------|------|
| S1 抓取 | 60s（长文 120s） | arXiv 元数据 + PDF |
| S2 解析 | 120s | pdfplumber |
| S3 摘要 | 60s | 本地规则抽取 |
| S4 RAG | 3s（检索） | 本地关键词检索 |
| 端到端 | 30s（含生成） | 样例模式无 LLM 生成 |

## 3. 三篇全链路演示（H088）

```bash
cd PaperPipeline
set PYTHONPATH=src
python test/pipeline/run_full_demo.py
```

产出：

- `data/demo/P1_1706.03762.json`
- `data/demo/P2_1810.04805.json`
- `data/demo/P7_2005.11401.json`
- `data/demo/demo_summary.json`

## 4. 瓶颈与优化预留

| 瓶颈 | 当前 | 对接后优化 |
|------|------|------------|
| PDF 下载 | 网络 IO | C 侧缓存 `PaperContent.storage_path` |
| 解析 | 单线程 pdfplumber | 成员 C 异步 `ParseTask` worker |
| 摘要 | 规则截取 | 成员 A/B LLM 服务 + Key 管理 |
| 检索 | 关键词 | C `POST /search/chunks` 向量检索 |
| QA 生成 | 模板回答 | 远程 LLM + 引用后处理 |

## 5. 无 Key 演示说明

设置 `PAPERMATE_QA_MODE=sample`（默认）即可在无 API Key 环境完成：

- 管线状态可达 `qa_ready`
- QA 返回可核验 `chunk_id` 引用
- 失败样例 P9/P10 正确拒绝

正式环境切换：设置 `PAPERMATE_API_BASE` 与 `PAPERMATE_QA_MODE=remote`（待 C/A 交付）。
