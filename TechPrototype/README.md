# TechPrototype

技术迭代相关代码与文档（界面原型仍在仓库根目录 `UIPrototype/`）。

| 子目录 | 说明 |
|--------|------|
| `backend/` | FastAPI 后端 |
| `PaperPipeline/` | 论文抓取 / 解析 / Worker 流水线 |
| `deploy/` | 打包、Nginx/systemd 样例、主机部署脚本 |
| `docs/` | 架构与部署说明 |

常用命令（在仓库根目录）：

```bash
python TechPrototype/deploy/pack.py
cd TechPrototype/backend && python -m uvicorn app.main:app --reload
```
