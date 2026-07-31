# source — PaperMate 可运行源代码

前后端与流水线已合并到本目录（原 `TechPrototype/` + `UIPrototype/frontend`）。

| 子目录 | 说明 |
|--------|------|
| `backend/` | FastAPI 后端；pytest 在 `backend/tests/` |
| `frontend/` | React + Vite 前端 |
| `PaperPipeline/` | 论文抓取 / 解析 Worker 流水线 |
| `deploy/` | 打包、Docker、Nginx、主机部署 |

## 本地开发

```bash
# 后端
cd FinalRelease/source/backend
python -m uvicorn app.main:app --reload

# 前端（另开终端）
cd FinalRelease/source/frontend
npm install && npm run dev
```

## 打包

```bash
python FinalRelease/source/deploy/pack.py
```

部署文档见 [../docs/others/部署说明.md](../docs/others/部署说明.md)。
