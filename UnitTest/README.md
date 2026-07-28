# UnitTest — PaperMate 单元测试

本目录为**课程交付入口**，汇总前后端单元测试说明与报告索引。  
实际测试代码仍在各模块源码树内，不在此重复存放。

## 与 SystemTest 的区别

| 类型 | 目录 | 目标 | 覆盖率要求 |
|------|------|------|------------|
| **单元测试** | `UnitTest/`（本目录）、`TechPrototype/backend/tests`、`UIPrototype/frontend/src/**/*.test.*` | 函数/模块级正确性 | 语句覆盖率 **>90%**（按模块或专项范围验收） |
| **系统测试** | [`SystemTest/`](../SystemTest/) | 端到端功能、易用性、兼容性 | 对照 [`docs/系统测试用例.xlsx`](../docs/系统测试用例.xlsx) |

## 目录

| 路径 | 说明 |
|------|------|
| [`backend/`](./backend/) | 后端单元测试报告与复现说明 |
| [`frontend/`](./frontend/) | 前端 Vitest 单元测试说明 |

## 后端（当前已验收）

- **报告**：[`TechPrototype/backend/UNIT_TEST_REPORT.md`](../TechPrototype/backend/UNIT_TEST_REPORT.md)
- **测试代码**：`TechPrototype/backend/tests/`
- **专项覆盖率脚本**：`TechPrototype/backend/scripts/run_search_coverage.sh`
- **结论**：智能检索核心模块语句覆盖率 **94.14%**（>90%）

```bash
cd TechPrototype/backend
python -m pip install -e ".[dev]"
bash scripts/run_search_coverage.sh   # Linux/macOS
# 报告输出到 TechPrototype/backend/reports/（本地生成，已 gitignore）
```

## 前端

- **测试代码**：`UIPrototype/frontend/src/**/*.test.{js,jsx}`
- **运行**：

```bash
cd UIPrototype/frontend
npm install
npm run test:run          # 执行测试
npm run test:coverage     # 生成覆盖率（输出到 coverage/，已 gitignore）
```

## 本地报告归档（可选）

若在本地生成 HTML/XML 覆盖率，可放入：

- `UnitTest/backend/reports/` — 后端 Cobertura / HTML
- `UnitTest/frontend/reports/` — 前端 Vitest HTML

上述 `reports/` 目录仅作工作区归档，默认不提交 Git。
