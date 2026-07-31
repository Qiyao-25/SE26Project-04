# PaperMate 系统测试执行报告

- 批次：`20260728-114548`
- 环境：`http://10.119.9.119`
- xlsx 用例数：69
- 本轮：通过 **60** / 失败 **2** / 未执行 **7**

## 文件夹

- `api/` pytest 日志与 junit
- `screenshots/` UI 截图（TC-xxx_*.png）
- `compatibility/` 浏览器与分辨率截图
- `docs/` 手工清单副本与错误日志
- `系统测试执行结果.xlsx` 回填结果簿

## 明细

| TC | Status | Evidence |
|----|--------|----------|
| TC-001 | Y | TC-001_register_form.png, TC-001_after_register.png |
| TC-002 | Y | TC-002_mismatch.png |
| TC-003 | Y | api/junit.xml |
| TC-004 | Y | TC-004_workspace.png |
| TC-005 | Y | TC-005_wrong_password.png |
| TC-006 | Y | TC-006_redirect.png |
| TC-007 | Y | TC-007_logout.png |
| TC-008 | Y | TC-008_workspace.png |
| TC-009 | Y | TC-009_reco_fail.png |
| TC-010 | Y | TC-010_search.png |
| TC-011 | Y | TC-011_nohit.png |
| TC-012 | Y | TC-012_empty.png |
| TC-013 | Y | api/junit.xml |
| TC-014 | Y | TC-014_detail.png |
| TC-015 | Y | TC-015_missing.png |
| TC-016 | Y | TC-016_learning.png, TC-016_back.png |
| TC-017 | Y | TC-017_exit.png |
| TC-018 | B | 需 pending 解析任务样例 |
| TC-019 | Y | TC-019_body.png |
| TC-020 | B | 需无 PDF 论文样例 |
| TC-021 | B | 全屏 Esc 需人工点按 |
| TC-022 | Y | TC-022_summary.png |
| TC-023 | Y | api/junit.xml |
| TC-024 | Y | api/junit.xml |
| TC-025 | Y | TC-025_graph.png |
| TC-026 | Y | api/junit.xml |
| TC-027 | N | TC-027_failed.png |
| TC-028 | Y | api/junit.xml |
| TC-029 | Y | api/junit.xml |
| TC-030 | Y | api/junit.xml |
| TC-031 | Y | api/junit.xml |
| TC-032 | Y | api/junit.xml |
| TC-033 | Y | api/junit.xml |
| TC-034 | B | PDF 划选批注依赖 PDF.js 文本层交互 |
| TC-035 | B | 批注无摘录校验依赖划选 |
| TC-036 | Y | api/junit.xml |
| TC-037 | Y | api/junit.xml |
| TC-038 | Y | api/junit.xml |
| TC-039 | Y | TC-039_learning.png |
| TC-040 | Y | api/junit.xml |
| TC-041 | Y | api/junit.xml |
| TC-042 | Y | api/junit.xml |
| TC-043 | Y | TC-043_settings.png |
| TC-044 | B | 单篇抓取依赖外网 arXiv |
| TC-045 | Y | api/junit.xml |
| TC-046 | Y | api/junit.xml |
| TC-047 | Y | api/junit.xml |
| TC-048 | Y | TC-048_admin.png |
| TC-049 | Y | api/junit.xml |
| TC-050 | Y | TC-050_library.png |
| TC-051 | Y | TC-051_quality_or_admin.png |
| TC-052 | Y | TC-052_workspace.png |
| TC-053 | Y | TC-053_sidebar.png |
| TC-054 | B | 本轮未覆盖 |
| TC-055 | Y | TC-055_states.png |
| TC-056 | Y | TC-056_mainpath.png |
| TC-057 | Y | TC-057_chromium.png |
| TC-058 | Y | TC-057_chromium.png |
| TC-059 | Y | TC-059_firefox.png |
| TC-060 | N | Safari 需 macOS |
| TC-061 | Y | TC-061_1080p.png, TC-061_1366.png, TC-061_1440.png |
| TC-062 | Y | TC-061_1080p.png, TC-061_1366.png, TC-061_1440.png |
| TC-063 | Y | reached http://10.119.9.119 |
| TC-064 | Y | api search in pytest.log |
| TC-065 | Y | TC-019_body.png |
| TC-066 | Y | api/junit.xml |
| TC-067 | Y | api/junit.xml |
| TC-068 | Y | TC-068_refresh.png |
| TC-069 | Y | TC-069_health.png |

## 说明

- 按决策**未做邮箱验证码**。
- `B` 表示本轮缺少特定数据/故障注入，未强行记失败。
- Safari（TC-060）在 Windows 执行机不可测，记 N。
- Edge（TC-058）以 Chromium 证据等价通过。
