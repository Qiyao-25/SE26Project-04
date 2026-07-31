# 单元测试 — PaperMate

报告与脚本归档目录（原 `UnitTest/`）。**测试源码**在 `FinalRelease/source/backend/tests/` 与 `FinalRelease/source/frontend/`。

## 目录

```
unit/
├── backend/          # 报告与说明（UNIT_TEST_REPORT.md）
├── frontend/         # 前端 Vitest 说明
└── scripts/          # run_backend_unit_tests.ps1
```

## 运行

```bash
# 智能检索专项 + 覆盖率门禁
cd FinalRelease/source/backend && bash scripts/run_search_coverage.sh

# 全量回归
cd FinalRelease/source/backend && python -m pytest

# Windows 一键
powershell -File FinalRelease/Test/unit/scripts/run_backend_unit_tests.ps1
```

## 与 system 测试的区别

| 类型 | 目录 | 目标 |
|------|------|------|
| 单元测试 | `unit/` + `source/*/tests` | 语句覆盖率 >90% |
| 系统测试 | [`system/`](../system/) | [系统测试用例.xlsx](../docs/系统测试用例.xlsx) |
