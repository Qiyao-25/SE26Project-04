# 后端单元测试

## 正式报告

见仓库内文档：[`TechPrototype/backend/UNIT_TEST_REPORT.md`](../../TechPrototype/backend/UNIT_TEST_REPORT.md)

| 指标 | 结果 |
|------|------|
| 覆盖范围 | `search_query_normalize.py` + `search_session_store.py` |
| 语句覆盖率 | **94.14%** |
| 专项用例 | 19 passed |
| 全量回归 | 122 passed, 2 skipped |

## 测试代码位置

```
TechPrototype/backend/
├── tests/                          # pytest 用例
│   ├── test_search_query_normalize_unit.py
│   ├── test_http_security.py
│   ├── test_http_api.py
│   └── ...
├── scripts/
│   ├── run_search_coverage.sh      # 智能检索专项 + 覆盖率门禁
│   └── start-api.sh                # Docker 启动前迁移
└── UNIT_TEST_REPORT.md             # 本模块验收报告（权威副本）
```

## 复现

```bash
cd TechPrototype/backend
python -m pip install -e ".[dev]"
python -m pytest -q
bash scripts/run_search_coverage.sh
```

生成物（本地，不提交）：

- `reports/junit-search.xml`
- `reports/coverage-search.xml`
- `reports/coverage-html/index.html`

也可复制到本目录 `reports/` 便于课程打包归档。
