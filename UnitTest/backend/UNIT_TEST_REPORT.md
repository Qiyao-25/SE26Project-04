# 后端单元测试报告

## 结论

后端智能检索内核的语句覆盖率为 **98.40%**，高于 90% 的验收要求；覆盖率命令启用了 `--cov-fail-under=90`，低于阈值时会返回非零退出码并使任务失败。

本报告的覆盖范围是主页「智能论文检索」的确定性核心，而非整个后端：

- `app/service/search_query_normalize.py`
- `app/service/search_session_store.py`

整套后端还包含需要外部网络、PDF、LLM、调度器和数据库运维环境的模块；本报告对可重复执行的检索逻辑做单元测试，并保留全量回归作为额外验证。

## 执行环境

| 项目 | 值 |
|---|---|
| 测试框架 | pytest |
| 覆盖率工具 | pytest-cov / coverage.py |
| 执行日期 | 2026-07-28 |
| 报告格式 | JUnit XML、Cobertura Coverage XML、Coverage HTML |

## 覆盖率结果（智能检索专项）

| 模块 | 语句数 | 未覆盖 | 语句覆盖率 |
|---|---:|---:|---:|
| `search_query_normalize.py` | 202 | 4 | 98.02% |
| `search_session_store.py` | 48 | 0 | 100.00% |
| **合计** | **250** | **4** | **98.40%** |

智能检索专项：**19 passed**（`test_search_query_normalize_unit.py` + `test_smart_search.py`）

## 测试代码位置

| 路径 | 说明 |
|------|------|
| `TechPrototype/backend/tests/` | 全部 pytest 用例 |
| `TechPrototype/backend/tests/conftest.py` | 共享 TestClient / DB fixtures |
| `TechPrototype/backend/tests/test_http_routes.py` | FastAPI 路由级 HTTP 测试 |
| `TechPrototype/backend/tests/test_search_query_normalize_unit.py` | 智能检索专项（覆盖率门禁） |
| `TechPrototype/backend/.coveragerc` | 全量覆盖率统计配置 |

## 复现命令

**智能检索专项（>90% 门禁）：**

```bash
cd TechPrototype/backend
python -m pip install -e ".[dev]"
bash scripts/run_search_coverage.sh
```

**全量后端回归：**

```bash
cd TechPrototype/backend
python -m pytest
```

Windows 一键脚本见 [`UnitTest/scripts/run_backend_unit_tests.ps1`](../scripts/run_backend_unit_tests.ps1)。

## 报告输出目录

脚本与全量覆盖率 HTML/XML 统一写入：

- `UnitTest/backend/reports/junit-search.xml`
- `UnitTest/backend/reports/coverage-search.xml`
- `UnitTest/backend/reports/coverage-html/index.html`
- `UnitTest/backend/reports/junit-full.xml`（全量回归时）

`reports/` 为本地生成目录，已 gitignore；本 Markdown 与测试代码随仓库提交。
