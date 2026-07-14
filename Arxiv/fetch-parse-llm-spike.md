# 抓取 / 解析 / 摘要 Spike 结果记录（H017–H018）

| 项 | 内容 |
|----|------|
| 任务 | **H017**（上午）+ **H018**（下午） |
| 日期 | 2026-07-15 |
| 负责人 | 成员 D |
| 脚本 | `SE26Project-04/Arxiv/scripts/spike_one_paper.py` |
| 依赖 | `pypdf`（见 `requirements-spike.txt`） |
| 样例 | **P1** `1706.03762`（Attention Is All You Need） |
| 同步源 | `ppp/TechPrototype/`（2026-07-14 同步） |

---

## 1. 可复现命令

在 `SE26Project-04/Arxiv/` 目录执行：

```powershell
# 安装依赖（一次性）
pip install -r requirements-spike.txt

# H017：按关键词抓取 1 篇元数据
$env:PYTHONIOENCODING='utf-8'
python scripts/spike_one_paper.py fetch --keyword "attention is all you need"

# H018：P1 全链路（抓取 → 下载 PDF → 解析 → 摘要）
python scripts/spike_one_paper.py pipeline --arxiv-id 1706.03762
```

**产物路径**（本目录）：

| 类型 | 路径 |
|------|------|
| H017 原始输出 | `data/h017_fetch.json` |
| H018 原始输出 | `data/h018_pipeline.json` |
| 运行归档 | `data/runs/run_20260714T070727Z.json`（首次含下载耗时） |
| PDF | `data/pdfs/1706.03762v7.pdf`（亦有 `PDF/` 样例存档） |

---

## 2. H017 结果（关键词抓取）

| 项 | 值 |
|----|-----|
| 关键词 | `attention is all you need` |
| 耗时 | **1.62s**（元数据 API） |
| 状态 | `ok` |
| 返回字段 | arxiv_id、title、authors、abstract、categories、pdf_url、abs_url |

> 关键词检索命中首条为 `2105.02723v1`（与 P1 不同属正常）。H018 贯通使用冻结样例 **P1** 固定 ID，避免样例漂移。

---

## 3. H018 结果（P1 全链路）

**论文**：Attention Is All You Need · `1706.03762v7` · 15 页 · 正文 **39,611** 字符

### 3.1 各阶段耗时（首次冷启动 run）

| 阶段 | 耗时 | 阈值 | 状态 | 说明 |
|------|------|------|------|------|
| fetch_metadata | 2.12s | ≤10s | `ok` | arXiv Atom API |
| download_pdf | **28.40s** | ≤60s | `ok` | 约 2.1MB PDF |
| parse_pdf | 2.17s | ≤90s | `ok` | pypdf 全文提取 |
| summarize | &lt;0.01s | ≤60s | `ok` | 抽取式摘要（无 LLM Key） |
| **端到端** | **~32.7s** | — | `summarized` | 四阶段全部通过 |

### 3.2 结构化输出（三件套）

| 字段 | 非空 | 说明 |
|------|------|------|
| `summary` | ✅ | 以 abstract + 引言高分句拼接 |
| `concept` | ✅ | 含 Transformer / Self-attention / Multi-Head 要点 |
| `methods` | ✅ | 从正文 methods/architecture 段抽取 |

完整 JSON 见 `data/runs/run_20260714T070727Z.json` 的 `structured` 字段。

### 3.3 已知限制（Spike 记录，非阻塞）

| # | 现象 | 影响 | 后续 |
|---|------|------|------|
| 1 | PDF 作者行含特殊 Unicode（如 ∗） | Windows 控制台 GBK 打印报错 | 已用 `PYTHONIOENCODING=utf-8`；结果写 JSON 文件 |
| 2 | 摘要为**抽取式**非 LLM | 质量低于最终产品 | H067 起接 Top-K + 生成；本日仅验证管线可贯通 |
| 3 | arXiv 返回 ID 带版本后缀 `v7` | 与清单 `1706.03762` 等价 | 入库时规范化为 base id |

---

## 4. 跑分表回填（P1）

| SpikeID | 实际耗时 | 实际状态 | Pass/Fail | 备注 |
|---------|----------|----------|-----------|------|
| S1-P1 | 30.5s（元数据+PDF） | `fetched` | **Pass** | 首次冷启动 |
| S2-P1 | 2.17s | `parsed` | **Pass** | 39k 字符 |
| S3-P1 | &lt;0.01s | `summarized` | **Pass** | 抽取式三件套 |

已同步至 [技术Spike清单.md](./技术Spike清单.md) 跑分表。

---

## 5. 验收结论

| 任务 | DoD | 结论 |
|------|-----|------|
| H017 | 命令可复现；返回 ID/标题/作者/摘要/PDF 地址 | **通过** |
| H018 | 至少 1 篇贯通；记录耗时与失败点 | **通过**（P1，无失败阶段） |

---

## 6. 明日入口（H027）

- 将本管线步骤画入活动图（fetch → download → parse → summarize → 入库占位）
- 序列图补充：超时、重试、失败状态名与 Spike 清单对齐
