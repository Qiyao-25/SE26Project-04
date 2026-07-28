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

## 约定

- 用例 ID 与 xlsx 一致：`TC-001` … `TC-069`
- pytest 用例名或标记含 `tc_001` / `@pytest.mark.tc("TC-001")`
- 仅 API 能覆盖的步骤写入 `api/`；UI 划选、浏览器兼容等写入 `manual/`
- 执行后在 `results/` 留报告；回填「是否通过」用 `Y`/`N`（与 Information 页统计公式一致）
