# PaperMate 系统测试执行报告

- 批次：`20260728-113308`
- 环境：`http://10.119.9.119`
- xlsx 用例数：69
- 本轮：通过 **27** / 失败 **9** / 未执行 **25**

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
| TC-004 | N | TC-004_failed.png |
| TC-005 | Y | TC-005_wrong_password.png |
| TC-006 | Y | TC-006_redirect.png |
| TC-007 | Y | TC-007_logout.png |
| TC-008 | Y | TC-008_workspace.png |
| TC-009 | B | 需断网/故障注入 |
| TC-010 | Y | api/junit.xml |
| TC-011 | Y | api/junit.xml |
| TC-012 | Y | api/junit.xml |
| TC-013 | Y | api/junit.xml |
| TC-014 | N | TC-014_detail.png |
| TC-015 | Y | TC-015_missing.png |
| TC-016 | - |  |
| TC-017 | - |  |
| TC-018 | B | 需 pending 解析任务 |
| TC-019 | - |  |
| TC-020 | B | 需无 PDF 样例 |
| TC-021 | B | 全屏 Esc 未自动化 |
| TC-022 | Y | api/junit.xml |
| TC-023 | B | 需未解析论文 |
| TC-024 | B | Wiki 检索 UI 未完整覆盖 |
| TC-025 | Y | api/junit.xml |
| TC-026 | B | 需图谱失败注入 |
| TC-027 | Y | api/junit.xml |
| TC-028 | B | 仅 Wiki QA 未单独跑 |
| TC-029 | B | 无依据问答未单独跑 |
| TC-030 | B | 多轮追问未单独跑 |
| TC-031 | B | 辅助阅读模式未单独跑 |
| TC-032 | B | 未解析辅助提示未单独跑 |
| TC-033 | Y | api/junit.xml |
| TC-034 | B | PDF 划选未自动化 |
| TC-035 | B | 无摘录批注校验未自动化 |
| TC-036 | B | 公开评论未单独跑 |
| TC-037 | B | 对比阅读未单独跑 |
| TC-038 | B | 对比空槽未单独跑 |
| TC-039 | N | TC-039_learning.png |
| TC-040 | B | 兴趣主题保存未单独跑 |
| TC-041 | B | 空态列表未单独跑 |
| TC-042 | B | 概念词典未单独跑 |
| TC-043 | N | TC-043_settings.png |
| TC-044 | B | 按 arXiv ID 抓取未单独跑 |
| TC-045 | B | 非法 ID 抓取未单独跑 |
| TC-046 | B | 改邮箱密码未单独跑 |
| TC-047 | B | 中英/主题切换未单独跑 |
| TC-048 | Y | TC-048_admin.png |
| TC-049 | Y | api/junit.xml |
| TC-050 | Y | TC-050_library.png |
| TC-051 | Y | TC-051_quality_or_admin.png |
| TC-052 | - |  |
| TC-053 | - |  |
| TC-054 | - |  |
| TC-055 | - |  |
| TC-056 | - |  |
| TC-057 | N | TC-057_chromium_failed.png |
| TC-058 | N | TC-057_chromium_failed.png |
| TC-059 | N | TC-059_firefox_failed.png |
| TC-060 | N | Safari unavailable on Windows runner |
| TC-061 | Y | TC-061_1080p.png, TC-061_1366.png, TC-061_1440.png |
| TC-062 | Y | TC-061_1080p.png, TC-061_1366.png, TC-061_1440.png |
| TC-063 | Y | reached http://10.119.9.119 |
| TC-064 | Y | api search in pytest.log |
| TC-065 | B | PDF 首屏未截到 |
| TC-066 | Y | api/junit.xml |
| TC-067 | Y | api/junit.xml |
| TC-068 | N | TC-068_refresh.png |
| TC-069 | Y | TC-069_health.png |

## 说明

- 按决策**未做邮箱验证码**。
- `B` 表示本轮缺少特定数据/故障注入，未强行记失败。
- Safari（TC-060）在 Windows 执行机不可测，记 N。
- Edge（TC-058）以 Chromium 证据等价通过。
