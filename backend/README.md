# PaperMate Backend

07-15 后端最小可运行闭环，包含：

- FastAPI GET /health、/docs 和 /openapi.json
- Pydantic Settings 的 dev/test 配置
- SQLAlchemy 2.x ORM 与 H005 核心实体
- Alembic 首次迁移、升级和回滚
- 统一响应模型与请求 ID
- python -m harness 可重复验收入口

## 1. 安装依赖

推荐在独立虚拟环境中执行：

    cd SE26Project-04/backend
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -e ".[dev]"

如果当前 Ubuntu 没有安装 python3-venv，可使用用户级安装：

    python3 -m pip install --user --break-system-packages -e ".[dev]"

## 2. 配置环境

    cp .env.example .env

默认使用 data/dev.db。测试使用内存 SQLite，不会污染开发数据库。PostgreSQL 只需替换：

    PAPERMATE_ENV=dev
    PAPERMATE_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/papermate

并安装 PostgreSQL 驱动：

    python -m pip install -e ".[postgres]"

## 3. 可重复执行命令

在 backend 目录、并且已激活 .venv 的情况下执行：

```bash
python -m harness health
python -m harness orm
python -m alembic upgrade head
python -m alembic current
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

首次启动建议先不使用 --reload，确认服务正常后再按需开启热重载。停止前台运行的服务可以直接按 Ctrl+C。

启动后访问：

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/openapi.json

### 3.1 检查并释放 8000 端口

如果出现 ERROR: [Errno 98] Address already in use，表示 8000 端口已经被某个进程监听。常见原因是之前启动的 Uvicorn 服务仍在运行，也可能是其他程序占用了该端口；这条错误本身不代表项目启动代码有问题。

先查询监听进程：

```bash
ss -ltnp 'sport = :8000'
```

如果当前用户看不到进程信息，再使用：

```bash
sudo ss -ltnp 'sport = :8000'
```

输出中的 users 字段会给出进程名和 PID，例如：

```text
users:(("python",pid=231978,fd=6))
```

终止前先确认 PID 确实属于目标 Uvicorn 进程：

```bash
ps -o pid,ppid,stat,cmd -p <PID>
```

如果使用了 --reload，Uvicorn 可能同时存在重载父进程和工作子进程。应先查看相关进程：

```bash
ps -ef | grep -E '[u]vicorn|[p]ython.*app.main'
```

正常终止目标进程：

```bash
kill -TERM <PID>
```

如果 STAT 字段包含 T，说明进程处于暂停状态，需要先恢复再终止：

```bash
kill -CONT <PID>
kill -TERM <PID>
```

再次检查端口：

```bash
ss -ltnp 'sport = :8000'
```

没有输出表示 8000 端口已经没有监听进程。只有在进程无法正常退出时，才使用最后手段：

```bash
kill -KILL <PID>
```

端口释放后重新启动服务：

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3.2 验证服务是否真正可用

端口释放或服务启动成功后，使用 HTTP 请求验证，而不是只看端口是否被监听：

```bash
curl -f http://127.0.0.1:8000/health
curl -I http://127.0.0.1:8000/docs
curl -f http://127.0.0.1:8000/openapi.json
```

如果端口可以连接但请求一直没有响应，通常是旧的 Uvicorn reload 进程处于暂停或失去响应状态；按照上面的进程状态检查和终止步骤清理后再启动。

## 4. 迁移升级、回滚和测试

```bash
python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head
python -m pytest --capture=no
```

迁移命令的预期结果是：第一次升级到 0001_initial_schema (head)，回滚后恢复为空库，再次升级成功。测试中的 StarletteDeprecationWarning 是依赖兼容性警告，不代表测试失败；以最后的 passed 数量和退出码为准。

## 5. 分层约定

    app/api         HTTP 路由、请求 ID、异常映射
    app/schema      请求/响应 DTO 和统一响应模型
    app/service     健康检查等业务用例
    app/repository  数据访问边界
    app/model       SQLAlchemy ORM 模型
    app/core        配置和数据库连接
    harness         固定命令、场景编排和验收输出

Harness 只编排和验证，不复制 service 业务规则；后续论文导入、解析和检索都应沿用这一边界。

## 6. 前端联调接口

后端现在提供固定样例论文的 HTTP API，供 React 前端在 `VITE_USE_MOCK=false` 时调用：

```text
POST /api/papers/search
GET  /api/papers/{paper_id}
GET  /api/papers/{paper_id}/content
GET  /api/papers/{paper_id}/summary
POST /api/papers/{paper_id}/qa
```

启动后可在 `http://127.0.0.1:8000/docs` 直接检查和调用。当前 repository 使用固定样例数据，后续可替换为 SQLAlchemy 数据库查询而不改变前端接口。
