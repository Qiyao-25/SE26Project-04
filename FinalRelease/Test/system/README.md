# 系统测试 — PaperMate

系统测试工件（原 `SystemTest/`），与 `FinalRelease/source/backend/tests/`（单元/接口 pytest）分离。

## 运行

```bash
cd FinalRelease/Test/system
python -m pytest api -q

# 全量（API + Playwright + xlsx 回填）
python scripts/run_full_system_test.py
```

Windows API 冒烟：

```powershell
powershell -File FinalRelease\Test\system\scripts\run_api_tests.ps1
```

最新归档结果见 [`results/latest-full/`](results/latest-full/)。
