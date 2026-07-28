# TC 覆盖对照（相对 docs/系统测试用例.xlsx）
# 自动化 = SystemTest/api；手工 = SystemTest/manual

| TC | 类型 | 方式 | 说明 |
|----|------|------|------|
| TC-001 | 功能 | API | 注册成功 |
| TC-002 | 功能 | 手工/前端 | API 无确认密码字段，校验在前端 |
| TC-003 | 功能 | API | 非法邮箱/短密码 |
| TC-004 | 功能 | API | 登录成功 |
| TC-005 | 功能 | API | 错误密码 |
| TC-006 | 功能 | API+手工 | API 无 token 访问受保护接口；路由跳转需浏览器 |
| TC-007 | 功能 | API+手工 | 登出后 token 失效；侧栏退出需浏览器 |
| TC-008 | 功能 | API | 三路推荐接口 |
| TC-009 | 功能 | 手工 | 需断网/故障注入 |
| TC-010 | 功能 | API | 智能检索 |
| TC-011 | 功能 | API | 无匹配 |
| TC-012 | 功能 | API+手工 | API 空查询；UI 拦截需浏览器 |
| TC-013 | 功能 | API | 检索分页（search_session） |
| TC-014 | 功能 | API | 论文详情 |
| TC-015 | 功能 | API | 论文不存在 |
| TC-016–TC-021 | 功能 | 手工 | PDF/页签/全屏/锁定为 UI |
| TC-022–TC-023 | 功能 | API | summary/wiki 状态 |
| TC-024 | 功能 | 手工/部分 API | Wiki 检索 UI 为主 |
| TC-025–TC-026 | 功能 | API | graph 接口 |
| TC-027–TC-032 | 功能 | API/手工 | QA/辅助依赖 LLM，有则测 |
| TC-033–TC-038 | 功能 | API/手工 | 笔记/评论/对比 |
| TC-039–TC-047 | 功能 | API/手工 | 学习/订阅/设置 |
| TC-048–TC-051 | 功能 | API | 管理员权限与论文库（需管理员账号） |
| TC-052–TC-056 | 易用性 | 手工 | 见 manual/usability.md |
| TC-057–TC-063 | 兼容性 | 手工 | 见 manual/compatibility.md |
| TC-064–TC-065 | 性能 | 可选 | manual/optional.md |
| TC-066–TC-067 | 安全 | API | 权限与注入字符串 |
| TC-068–TC-069 | 可靠/安装 | 手工/可选 | 刷新会话、部署冒烟 |
