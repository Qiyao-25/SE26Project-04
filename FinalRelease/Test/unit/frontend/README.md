# 前端单元测试（Vitest）

- 配置：`FinalRelease/source/frontend/vitest.config.js`
- 用例：`FinalRelease/source/frontend/src/**/*.test.js`

## 运行

```bash
cd FinalRelease/source/frontend
npm run test
npm run test:coverage   # → coverage/（已 gitignore）
```

如需归档覆盖率 HTML，可复制到 `FinalRelease/Test/unit/frontend/reports/`。

页面级行为由 [`../system/`](../system/) 系统测试覆盖。
