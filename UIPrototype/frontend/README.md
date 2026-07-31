# PaperMate 界面原型迭代

基于 **React + React Router + Ant Design** 的前端工程，由 `prototype/` 线框图原型迭代而来。

## 技术栈

- React 19 + Vite
- React Router v7
- Ant Design 5 + @ant-design/icons

## 启动

```bash
cd 界面原型迭代
npm install
npm run dev
```

浏览器访问终端提示的本地地址（默认 `http://localhost:5173`）。

默认请求本地后端 `http://127.0.0.1:8000`。只演示前端原型时，可在 `.env.local` 设置 `VITE_USE_MOCK=true`；联调时保持默认值，先启动后端并执行 `python -m scripts.seed`。

## 工程分层

```
界面原型迭代/src/
├── routes/           # 路由与鉴权
├── layouts/          # 主布局（侧栏 + 顶栏）
├── pages/            # 页面级组件
│   ├── Login/
│   ├── Workspace/
│   ├── PaperDetail/
│   ├── Learning/
│   ├── Admin/
│   └── Settings/
├── components/       # 可复用组件
│   ├── auth/
│   ├── common/
│   └── paper/
├── context/          # 全局状态（登录、画像、笔记等）
├── data/             # 静态数据与 mock
├── utils/            # 工具函数
└── styles/           # 全局样式
```

## 页面映射

| 线框页面 | 路由 | 说明 |
|---------|------|------|
| 登录/注册 | `/login` | Tab 切换、首次引导弹窗 |
| 工作空间 | `/workspace` | 推荐论文、搜索问答、结果列表 |
| 论文详情 | `/paper/:paperId` | 左侧三 Tab + 右侧六栏侧栏 |
| 学习空间 | `/learning` | 收藏/笔记/历史/词典/画像/模式 |
| 管理员后台 | `/admin` | 六模块系统管理 |
| 设置 | `/settings` | 订阅/账户/网页 |

## 与线框图的关系

- `prototype/` 保留不动，作为低保真线框参考
- 本工程使用 Ant Design 组件库，布局与交互与线框一致，视觉为常规后台/内容平台风格
- 演示账号：任意邮箱登录；管理员：`admin`

## 构建

```bash
npm run build
npm run preview
```

## 前后端联调与 Mock 切换

1. 复制环境变量：

```powershell
Copy-Item .env.example .env.development
```

2. 默认 `VITE_USE_MOCK=false`，前端会请求 FastAPI：

```text
GET  /api/papers?keyword=attention&page=1&page_size=12
POST /api/papers/batch
GET  /api/papers/{paperId}
GET  /api/papers/{paperId}/content
GET  /api/papers/{paperId}/summary
GET  /api/papers/{paperId}/wiki
GET  /api/papers/{paperId}/graph
GET  /api/papers/{paperId}/assist
POST /api/papers/{paperId}/qa
```

3. 需要脱离后端演示时，将 `.env.development` 改为：

```env
VITE_USE_MOCK=true
```

4. 启动顺序：先在 `backend` 启动 Uvicorn（可配置 `PAPERMATE_LLM_API_KEY`），再在 `UIPrototype/frontend` 执行 `npm run dev`。登录、注册、账户修改和学习数据会通过后端保存；点击论文详情页的解析按钮后，由 FastAPI 当前进程直接执行解析，不需要另开 Worker。

## 生产构建

```bash
cp ../../deploy/env.frontend.production.example .env.production
npm ci
npm run build
```

将 `dist/` 交给 Nginx 托管，并配置 `/api` 反代到后端。完整步骤见仓库 `docs/部署说明.md`。

论文详情页点击「开始解析 / 重新解析」会创建任务；backend 内嵌 **Summarize Agent** 自动下载 PDF、生成智能总结并写回 `/summary`，前端轮询完成后刷新「智能总结」页。知识图谱、辅助阅读、Wiki 小检索、对比阅读、收藏、笔记和阅读历史也会在联调模式下调用真实后端接口。侧边栏「问答」会调用 **QA Agent**（检索原文块 + LLM 生成，带引用）。

工作台「智能论文检索」会调用 `POST /api/papers/smart-search`：**查询改写 → 多关键词模糊匹配 → 生成检索回答**（仅该搜索框接入；详情页 Wiki 小检索等不接 LLM）。
