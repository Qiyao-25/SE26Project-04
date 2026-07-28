# docs — 课程交付文档

本目录仅存放**与仓库交付物直接相关**的文档，不包含脚本或运行时产物。

| 文件 | 说明 |
|------|------|
| [`系统测试用例.xlsx`](./系统测试用例.xlsx) | 系统测试用例模板（69 条 TC） |

## 相关目录

- 系统测试执行脚本与结果 → [`SystemTest/`](../SystemTest/)
- 单元测试报告 → [`UnitTest/backend/UNIT_TEST_REPORT.md`](../UnitTest/backend/UNIT_TEST_REPORT.md)
- 架构/部署文档 → [`TechPrototype/docs/`](../TechPrototype/docs/)

## 维护说明

- 用例索引导出：`SystemTest/cases/export_cases.py`
- 结果回填：`SystemTest/scripts/write_results_xlsx.py`
- **勿**在本目录放置 `_fill_*.py` 等临时脚本（应放在 `SystemTest/scripts/`）
