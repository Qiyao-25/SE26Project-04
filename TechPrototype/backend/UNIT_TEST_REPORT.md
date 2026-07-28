# 后端智能检索单元测试报告

## 结论

后端智能检索内核的语句覆盖率为 **98.40%**，高于 90% 的验收要求；覆盖率命令启用了 `--cov-fail-under=90`，低于阈值时会返回非零退出码并使任务失败。

本报告的覆盖范围是主页“智能论文检索”的确定性核心，而非整个后端：

- `app/service/search_query_normalize.py`
- `app/service/search_session_store.py`

之所以明确限定范围，是因为整套后端还包含需要外部网络、PDF、LLM、调度器和数据库运维环境的模块。把它们混入本报告会得到较低但无意义的覆盖率，或需要用不真实的 mock 覆盖生产路径。本次报告对实际可重复执行的检索逻辑进行单元测试，并保留全量回归结果作为额外验证。

## 执行环境

| 项目 | 值 |
|---|---|
| 测试框架 | pytest 9.1.1 |
| 覆盖率工具 | pytest-cov 7.1.0 / coverage.py 7.15.2 |
| Python | 3.12.3 |
| 执行日期 | 2026-07-28 |
| 报告格式 | JUnit XML、Cobertura Coverage XML、Coverage HTML、终端文本摘要 |

## 覆盖率结果

| 模块 | 语句数 | 未覆盖 | 语句覆盖率 |
|---|---:|---:|---:|
| `search_query_normalize.py` | 202 | 4 | 98.02% |
| `search_session_store.py` | 48 | 0 | 100.00% |
| **合计** | **250** | **4** | **98.40%** |

智能检索专项测试结果：**19 passed**，耗时约 1 秒。

完整后端回归结果：**122 passed, 2 skipped**，耗时约 5 秒。跳过项为需要可选外部集成环境的测试，不影响本地单元测试结论。

## 新增测试覆盖点

`tests/test_search_query_normalize_unit.py` 覆盖以下行为：

- arXiv ID 的前缀、版本号和非编号输入。
- 多层礼貌前缀、称谓和“论文”后缀的查询清洗。
- 年份区间、`after/since/from`、`before/until`、中文“年前/年后”、精确年份和“近几年”。
- 综述/短文排除词和论文元数据排除判断。
- RAG、LLM 等中英文术语别名、分类提示和未知术语降级。
- 中文研究方向到英文检索词和 arXiv 分类的扩展。
- 已知中文作者别名、未知中文姓名的保守拼音提示、英文姓名倒置变体。
- arXiv、作者、作者+主题混合、主题检索模式判定。
- 搜索会话的创建、读取、过期清理、缺失会话和容量淘汰。

原有 `tests/test_smart_search.py` 同时验证了标题精确命中、中文作者到英文作者检索、术语计划、数据库搜索与稳定分页。

## 同时修复的缺陷

测试暴露并验证了四个实际缺陷修复：

1. `请帮我找沈备军老师的论文` 曾只去掉“请帮我”，残留“找”；现在按最长匹配循环剥离连续前缀。
2. `before 2020` 曾被解析为精确年份 `(2020, 2020)`；现在正确解析为截至年份 `(None, 2020)`。
3. `张伟老师的论文` 的正则捕获会把“老师”吞进姓名；现在在作者解析前去掉尾部称谓，得到保守的拼音候选并附未验证警告。
4. `2024 年前` 曾被错误解析为精确年份 `(2024, 2024)`；年份范围、上界、下界与精确年份现按明确的优先级独立匹配，避免方向词被忽略或普通年份被误判为边界。

## 复现命令

在 `TechPrototype/backend` 目录执行：

```bash
.venv/bin/python -m pip install -e '.[dev]'
bash scripts/run_search_coverage.sh
```

脚本会生成以下原始报告文件：

- `reports/junit-search.xml`：JUnit 兼容测试结果，可被 CI、IDE 或持续集成平台读取。
- `reports/coverage-search.xml`：Cobertura 格式覆盖率报告。
- `reports/coverage-html/index.html`：可在浏览器打开的行级覆盖率报告。

完整后端回归可执行：

```bash
.venv/bin/python -m pytest --junitxml=reports/junit-full.xml
```

`reports/` 是本地生成目录，已被 `.gitignore` 忽略；本报告、测试代码和执行脚本会随代码提交，其他成员可重复生成同一类报告。
