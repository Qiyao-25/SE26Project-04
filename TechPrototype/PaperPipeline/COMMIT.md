# PaperPipeline 提交方案

面向 `SE26Project-04` 仓库，与现有 `backend/`、`UIPrototype/`、`docs/` 并列交付。

## 命名说明

| 旧名 | 新名 | 原因 |
|------|------|------|
| `Arxiv` / `PartD` | **`PaperPipeline`** | 按功能命名（论文处理流水线），避免成员代号；与 `UIPrototype` 风格一致 |

本地备份：`ppp/PaperPipeline/`（不进 SE26 仓库）。

## 提交前检查

```powershell
cd SE26Project-04/PaperPipeline
$env:PYTHONPATH="src"; $env:PYTHONIOENCODING="utf-8"
python -m pipeline.worker.run_demo      # RESULT: PASS
python -m pipeline.qa.run_eval          # ≥18/20
python test/pipeline/run_full_demo.py   # 3/3
```

**不要提交：**

- `data/logs/`（运行时任务日志）
- 大体积 PDF（`data/**/pdfs/`，若存在）
- `.env`、本机绝对路径敏感信息（样例 JSON 中的 path 仅作相对参考）

建议在目录内保留 `.gitignore`（已提供）。

## 推荐提交方式（单提交）

与近期仓库风格一致（`feat: …`）：

```powershell
cd SE26Project-04

# 若仍残留旧目录 PartD，先关闭占用该目录的编辑器标签后再删除
if (Test-Path PartD) { Remove-Item -Recurse -Force PartD }

git add PaperPipeline/
git add README.md   # 仓库结构表已改为 PaperPipeline

git status
git commit -m "feat(PaperPipeline): 论文抓取解析摘要与出处问答流水线"
```

### 提交说明（可作 PR body）

```text
## Summary
- 新增 PaperPipeline：arXiv 抓取、PDF 解析、Wiki 三件套、带引用 QA、任务队列
- 字段对齐 backend ORM 与 UIPrototype mocks（integration/contracts.py）
- 含 Spike 文档、UML、≥100 seed、10 篇样例、20 题评测与三篇演示

## Test plan
- [ ] PYTHONPATH=src 下 run_demo / run_eval / run_full_demo 通过
- [ ] 不依赖 PAPERMATE_API_BASE 可本地演示
```

## 可选：拆成两笔（评审更清晰）

1. `feat(PaperPipeline): 管线骨架与样例/Spike/UML 数据`
2. `fix(PaperPipeline): 对齐 backend ORM 与 UI 引用字段`

当前目录为未跟踪整树时，**单提交更合适**。

## 推送与 PR（需你确认后再执行）

```powershell
git push -u origin HEAD
gh pr create --title "feat: PaperPipeline 论文处理流水线" --body "见 COMMIT.md"
```

## 与项目整体的关系

```text
UIPrototype  → 展示 / mock
backend      → API + ORM + 持久化
PaperPipeline→ 抓取/解析/摘要/QA（Worker；经 PAPERMATE_API_BASE 对接 C）
docs         → 需求与评审
```

联调顺序：`GET /health` → `POST /papers/batch` → chunks → QA/UI（见 INTEGRATION.md）。
