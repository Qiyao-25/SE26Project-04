# Arxiv Spike + UML 交付说明

与 `ppp/TechPrototype` 同步；**H017–H018 / H027–H028 已按 `backend` ORM 修订（V1.1）**。

| 文件 / 目录 | 说明 | 任务 |
|-------------|------|------|
| [10篇样例论文清单.md](./10篇样例论文清单.md) | 固定 10 篇样例 | H007–H008 |
| [技术Spike清单.md](./技术Spike清单.md) | 四阶段 Spike 定义 | H008 |
| [fetch-parse-llm-spike.md](./fetch-parse-llm-spike.md) | 贯通结果 + **backend 字段映射** | H017–H018 |
| [H017_上午验收.md](./H017_上午验收.md) / [H018_下午验收.md](./H018_下午验收.md) | 验收（含 `backend_paper` / `backend_upsert`） | H017–H018 |
| [scripts/spike_one_paper.py](./scripts/spike_one_paper.py) | Spike 脚本（输出对齐 ORM） | H017–H018 |
| [uml/](./uml/) | **H027/H028** 活动图/序列图（ParseTask / TextChunk / ApiResponse） | H027–H028 |
| `data/` | 运行产物 | H017–H018 |
| `PDF/` | 样例 PDF 存档 | H007+ |

Backend 依据：`SE26Project-04/backend/app/model/entities.py`（当前仅 `GET /health`）。

## 复现

```powershell
cd SE26Project-04/Arxiv
pip install -r requirements-spike.txt
$env:PYTHONIOENCODING='utf-8'
python scripts/spike_one_paper.py fetch --keyword "attention is all you need"
python scripts/spike_one_paper.py pipeline --arxiv-id 1706.03762

cd uml
python preview_check.py
```

UML 出图：https://mermaid.live （粘贴 `uml/pipeline-*.md` 中 mermaid 块）。
