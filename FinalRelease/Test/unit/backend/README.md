# 后端单元测试

## 正式报告

[`UNIT_TEST_REPORT.md`](./UNIT_TEST_REPORT.md) — 智能检索专项 **98.40%** 语句覆盖率（>90%）

## 测试代码（不在此目录重复存放）

```
FinalRelease/source/backend/tests/
├── conftest.py                         # 共享 fixtures
├── test_http_routes.py                 # FastAPI TestClient 路由覆盖
├── test_search_query_normalize_unit.py # 智能检索专项
├── test_http_security.py               # 鉴权/租约契约
└── …                                   # 其余 service/API 用例
```

## 运行

| 场景 | 命令 |
|------|------|
| 智能检索专项 + 覆盖率门禁 | `bash FinalRelease/source/backend/scripts/run_search_coverage.sh` |
| 全量回归 | `cd FinalRelease/source/backend && python -m pytest` |
| Windows 一键 | `powershell -File FinalRelease/Test/unit/scripts/run_backend_unit_tests.ps1` |

## 报告输出

写入 `FinalRelease/Test/unit/backend/reports/`（本地生成，不提交 Git）：

- `junit-search.xml` / `coverage-search.xml` / `coverage-html/`
- `junit-full.xml` / `coverage.xml`（全量回归时）
