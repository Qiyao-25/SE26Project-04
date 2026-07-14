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

在 backend 目录执行：

    python -m harness health
    python -m harness orm
    python -m alembic upgrade head
    python -m alembic current
    python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

启动后访问：

- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/openapi.json


如果遇到“ERROR:    [Errno 98] Address already in use”，可以：

查询运行端口：
- ss -ltnp | grep ':8000'

输出中会包含类似：users:(("python",pid=231978,fd=6))

然后运行：

```bash
    kill -TERM <pid>
```

确认端口释放：
- ss -ltnp | grep ':8000'

## 4. 迁移升级、回滚和测试

    python -m alembic upgrade head
    python -m alembic downgrade base
    python -m alembic upgrade head
    python -m pytest

## 5. 分层约定

    app/api         HTTP 路由、请求 ID、异常映射
    app/schema      请求/响应 DTO 和统一响应模型
    app/service     健康检查等业务用例
    app/repository  数据访问边界
    app/model       SQLAlchemy ORM 模型
    app/core        配置和数据库连接
    harness         固定命令、场景编排和验收输出

Harness 只编排和验证，不复制 service 业务规则；后续论文导入、解析和检索都应沿用这一边界。

