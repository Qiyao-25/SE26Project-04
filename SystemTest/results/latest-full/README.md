# 系统测试结果（latest-full）

本目录为最近一次完整系统测试批次的稳定入口（由 `full-run-*` 复制）。

## 内容

| 路径 | 说明 |
|------|------|
| `REPORT.md` | 执行总报告（69 条逐条状态） |
| `系统测试执行结果.xlsx` | 回填后的结果簿 |
| `SCREENSHOTS.md` | 截图索引 |
| `api/` | pytest junit + 日志 |
| `screenshots/` | 功能/易用性 UI 截图 |
| `compatibility/` | Chrome/Firefox/分辨率截图 |
| `docs/` | 手工清单副本与错误日志 |

复跑：在 `SystemTest/` 下执行 `python scripts/run_full_system_test.py`
