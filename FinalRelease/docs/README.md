# docs — 交付文档索引

本目录为 **FinalRelease 交付文档** 根目录；原仓库根 `docs/` 已并入此处。

## 内容

| 路径 | 说明 |
|------|------|
| [系统测试用例.xlsx](./系统测试用例.xlsx) | 课程系统测试用例模板 |
| [others/](./others/) | 部署说明、运维、GoF 设计、架构说明 |
| [UMLmodel/](./UMLmodel/) | UML / OOM 模型与 docx |
| [wireframe/](./wireframe/) | 早期线框原型（静态 HTML） |

## 相关目录

- 系统测试执行脚本与结果 → [`../Test/system/`](../Test/system/)
- 单元测试报告 → [`../Test/unit/backend/UNIT_TEST_REPORT.md`](../Test/unit/backend/UNIT_TEST_REPORT.md)
- 源代码 → [`../source/`](../source/)

## 维护约定

- 用例索引导出：`FinalRelease/Test/system/cases/export_cases.py`
- 结果回填：`FinalRelease/Test/system/scripts/write_results_xlsx.py`
- **勿**在本目录放置临时脚本（应放在 `FinalRelease/Test/system/scripts/`）
