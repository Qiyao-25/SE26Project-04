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
POST /api/papers/{paperId}/qa
```

3. 需要脱离后端演示时，将 `.env.development` 改为：

```env
VITE_USE_MOCK=true
```

4. 启动顺序：先在 `backend` 启动 Uvicorn，再在 `UIPrototype/frontend` 执行 `npm run dev`。
