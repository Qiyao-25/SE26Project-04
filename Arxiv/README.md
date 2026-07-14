# Arxiv Spike 交付说明

本文件夹存放技术 Spike 的**可验收输出**（与 `ppp/TechPrototype/docs/spike/` 同步）：

| 文件 / 目录 | 说明 | 任务 |
|-------------|------|------|
| [10篇样例论文清单.md](./10篇样例论文清单.md) | 固定 10 篇样例（正常 / 长文 / 公式表格 / 双栏 / 失败） | H007 → H008 冻结 |
| [技术Spike清单.md](./技术Spike清单.md) | 抓取、解析、摘要、问答：输入 / 预期输出 / 超时 / 失败判定 | **H008 终稿** |
| [fetch-parse-llm-spike.md](./fetch-parse-llm-spike.md) | H017/H018 贯通结果、命令、耗时 | **H017–H018** |
| [H017_上午验收.md](./H017_上午验收.md) | 关键词抓取验收 | H017 ✅ |
| [H018_下午验收.md](./H018_下午验收.md) | P1 全链路验收 | H018 ✅ |
| [在arXiv网站上做什么.md](./在arXiv网站上做什么.md) | 人工核对 ID / 体量 / 失败样例 | H007/H008 |
| [scripts/spike_one_paper.py](./scripts/spike_one_paper.py) | 抓取→解析→摘要 Spike 脚本 | H017–H018 |
| [requirements-spike.txt](./requirements-spike.txt) | Spike 依赖（pypdf） | H017–H018 |
| `data/` | 运行产物（JSON + P1 PDF） | H017–H018 |
| `PDF/` | 样例论文 PDF 存档 | H007+ |

## 完成标准对照

- [x] 样例含**正常**（P1、P2、P7）
- [x] 样例含**长文**（P5）
- [x] 样例含**公式 / 表格**（P3、P4）
- [x] 样例含**失败场景**（P9、P10）
- [x] 四阶段 Spike 均定义输入、预期输出、超时、失败判定
- [x] P1 抓取/解析/摘要实测（H017–H018）
- [ ] 跑分全覆盖（P2–P10 待跑）

## 复现命令（本目录）

```powershell
cd SE26Project-04/Arxiv
pip install -r requirements-spike.txt
$env:PYTHONIOENCODING='utf-8'
python scripts/spike_one_paper.py fetch --keyword "attention is all you need"
python scripts/spike_one_paper.py pipeline --arxiv-id 1706.03762
```
