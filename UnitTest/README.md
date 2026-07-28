# UnitTest — PaperMate 单元测试

课程交付的**单元测试**入口：报告、复现脚本与覆盖率归档位置。

## 目录

```
UnitTest/
├── README.md                          # 本文件
├── scripts/
│   └── run_backend_unit_tests.ps1     # Windows 全量/专项一键脚本
├── backend/
│   ├── UNIT_TEST_REPORT.md            # 后端验收报告（权威）
│   ├── README.md
│   └── reports/                       # 本地生成（gitignore）
└── frontend/
    ├── README.md
    └── reports/                       # 本地生成（gitignore）
```

## 与 SystemTest 的区别

| 类型 | 目录 | 验收依据 |
|------|------|----------|
| **单元测试** | `UnitTest/` + 各模块 `tests/` | 语句覆盖率 **>90%** |
| **系统测试** | [`SystemTest/`](../SystemTest/) | [`docs/系统测试用例.xlsx`](../docs/系统测试用例.xlsx) |

## 后端（已验收）

- **报告**：[`backend/UNIT_TEST_REPORT.md`](./backend/UNIT_TEST_REPORT.md)
- **测试代码**：`TechPrototype/backend/tests/`
- **智能检索覆盖率**：**98.40%**（专项门禁 `--cov-fail-under=90`）

```powershell
# Windows
powershell -File UnitTest/scripts/run_backend_unit_tests.ps1 -SearchOnly

# Linux/macOS
cd TechPrototype/backend && bash scripts/run_search_coverage.sh
```

## 前端

```bash
cd UIPrototype/frontend
npm run test:run
npm run test:coverage   # → UIPrototype/frontend/coverage/
```

详见 [`frontend/README.md`](./frontend/README.md)。
