# H027 / H028 · 依赖分析（V1.1 backend 对齐）

| 项 | 内容 |
|----|------|
| 结论 | **不强制依赖**业务 API 即可完成 UML；**已按 backend ORM 修订命名** |
| Backend 依据 | `SE26Project-04/backend/app/model/entities.py` + `schema/common.py` |

## 依赖

| 对象 | 是否阻塞 UML | 说明 |
|------|--------------|------|
| C：H015/H016 骨架 + ORM | **不阻塞画图**；**应用其对齐字段** | 表/字段已存在 |
| C：papers/tasks/qa 路由 | **不阻塞** | 图画目标契约；注明仅 health 已实现 |
| D：Spike H007–H018 | 需要，已有 | 超时与阶段名 |

## 修订相对 V1.0

| 旧称呼 | 新称呼（backend） |
|--------|-------------------|
| Task | **ParseTask** / `parse_tasks` |
| Chunk.page / text | **TextChunk.page_no / content** |
| 入库「占位」 | upsert **Paper + PaperContent + TextChunk + StructuredResult** |
| 裸 JSON 响应 | **ApiResponse** 信封 |

交付：`pipeline/pipeline-activity.md`、`pipeline/pipeline-sequence.md`。
