# SystemTest — PaperMate 系统测试工件

本目录存放依据 [`docs/系统测试用例.xlsx`](../docs/系统测试用例.xlsx) 开展的**系统测试**脚本、手工清单与执行结果。  
与 `TechPrototype/backend/tests`（单元/接口）分离。

## 目录

| 路径 | 说明 |
|------|------|
| `cases/case_index.json` | 从 xlsx 导出的 69 条用例索引 |
| `cases/export_cases.py` | 重新从 xlsx 导出索引 |
| `cases/coverage_matrix.md` | TC → 自动化/手工 覆盖对照 |
| `api/` | 可 API 自动化的功能用例（pytest + httpx） |
| `manual/` | 需浏览器的功能、易用性、兼容性清单 |
| `scripts/run_api_tests.ps1` | 一键跑 API 系统测并写结果摘要 |
| `scripts/write_results_xlsx.py` | 把执行结果回填到结果簿 |
| `results/` | 执行报告、回填后的结果 xlsx |

## 快速执行（API 自动化）

默认打演示站（需校园网/VPN）：

```powershell
cd SystemTest
$env:PAPERMATE_BASE_URL = "http://10.119.9.119"
$env:PAPERMATE_API_PREFIX = "/api"
powershell -File scripts\run_api_tests.ps1
```

本地后端：

```powershell
$env:PAPERMATE_BASE_URL = "http://127.0.0.1:8000"
$env:PAPERMATE_API_PREFIX = "/api"
powershell -File scripts\run_api_tests.ps1
```

## 最新完整执行结果

入口目录：[`results/latest-full/`](./results/latest-full/)

- 总报告：`REPORT.md`
- 回填结果簿：`系统测试执行结果.xlsx`
- 截图：`screenshots/`、`compatibility/`
- API 证据：`api/`

一键复跑：

```powershell
cd SystemTest
$env:PAPERMATE_BASE_URL = "http://10.119.9.119"
python scripts\run_full_system_test.py
```
