# 前端单元测试

## 框架

- **Vitest** + **@testing-library/react** + **jsdom**
- 配置：`UIPrototype/frontend/vitest.config.js`

## 测试文件

| 文件 | 覆盖对象 |
|------|----------|
| `src/services/authService.test.js` | 登录/注册 mock 路径 |
| `src/services/paperService.test.js` | 论文列表/检索/详情工具函数 |
| `src/components/paper/PaperCard.test.jsx` | 论文卡片组件渲染 |

## 运行

```bash
cd UIPrototype/frontend
npm install
npm run test:run
npm run test:coverage
```

覆盖率 HTML 默认输出到 `UIPrototype/frontend/coverage/`（已 gitignore）。  
如需归档，可复制到 `UnitTest/frontend/reports/`。

## 说明

前端当前覆盖率统计范围主要为 `services/` 与 `components/paper/`（见 `vitest.config.js` 的 exclude 列表）。  
页面级、路由级行为由 [`SystemTest/`](../SystemTest/) 的系统测试覆盖。
