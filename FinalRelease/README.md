# FinalRelease — PaperMate 最终交付目录

本目录集中存放课程/项目最终交付物：**源代码**、**测试**、**文档**。

## 目录结构

```
FinalRelease/
├── source/                 # 可运行源代码（原 TechPrototype + UIPrototype/frontend）
│   ├── backend/            # FastAPI 后端
│   ├── frontend/           # React 前端
│   ├── PaperPipeline/      # 论文抓取 / 解析流水线
│   └── deploy/             # 打包、Docker、Nginx、主机部署脚本
├── Test/
│   ├── system/             # 系统测试（原 SystemTest）
│   └── unit/               # 单元测试报告与脚本（原 UnitTest）
└── docs/                   # 交付文档、UML、部署说明、系统测试用例 xlsx
```

## 常用命令

```bash
# 打包部署（仓库根目录）
python FinalRelease/source/deploy/pack.py

# 启动后端
cd FinalRelease/source/backend && python -m uvicorn app.main:app --reload

# 启动前端
cd FinalRelease/source/frontend && npm run dev

# 系统测试 API
cd FinalRelease/Test/system && python -m pytest api -q

# 后端单元测试（Windows）
powershell -File FinalRelease/Test/unit/scripts/run_backend_unit_tests.ps1
```

文档索引见 [docs/README-root-index.md](./docs/README-root-index.md)。
