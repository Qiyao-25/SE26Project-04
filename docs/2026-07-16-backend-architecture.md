# PaperMate 后端数据库与联调基线

本文件记录当前可运行的后端最小闭环。数据库结构以 `backend/app/model/entities.py` 和 Alembic 迁移为准，接口字段以 FastAPI OpenAPI 为准。

## 领域分析类图

```mermaid
classDiagram
    class Paper {
        +int id
        +string arxiv_id [unique]
        +string title
        +string abstract
        +string ingest_status
    }
    class Author {
        +int id
        +string normalized_name [unique]
        +string display_name
    }
    class PaperAuthor {
        +int paper_id [PK/FK]
        +int author_id [PK/FK]
        +int author_order
    }
    class PaperContent { +int paper_id [PK/FK] +string checksum [unique] }
    class ParseTask { +int id +int paper_id [FK] +string status +string idempotency_key [unique] }
    class StructuredResult { +int id +int paper_id [FK] +string result_type +int version }
    class TextChunk { +int id +int paper_id [FK] +string chunk_id +int page_no }
    class UserAction { +int id +string user_id +int paper_id [FK] +string action_type }
    Paper "1" --> "0..*" PaperAuthor
    Author "1" --> "0..*" PaperAuthor
    Paper "1" --> "0..1" PaperContent
    Paper "1" --> "0..*" ParseTask
    Paper "1" --> "0..*" StructuredResult
    Paper "1" --> "0..*" TextChunk
    Paper "1" --> "0..*" UserAction
    ParseTask "0..1" --> "0..*" StructuredResult
```

## ER 与约束

```mermaid
erDiagram
    PAPERS ||--o{ PAPER_AUTHORS : has
    AUTHORS ||--o{ PAPER_AUTHORS : writes
    PAPERS ||--o| PAPER_CONTENTS : stores
    PAPERS ||--o{ PARSE_TASKS : schedules
    PAPERS ||--o{ STRUCTURED_RESULTS : produces
    PARSE_TASKS o|--o{ STRUCTURED_RESULTS : creates
    PAPERS ||--o{ TEXT_CHUNKS : splits
    PAPERS ||--o{ USER_ACTIONS : records
    PAPERS { int id PK string arxiv_id UK string title string primary_category }
    AUTHORS { int id PK string normalized_name UK string display_name }
    PAPER_AUTHORS { int paper_id PK,FK int author_id PK,FK int author_order }
    PAPER_CONTENTS { int paper_id PK,FK string checksum UK string storage_path }
    PARSE_TASKS { int id PK int paper_id FK string status string idempotency_key UK }
    STRUCTURED_RESULTS { int id PK int paper_id FK string result_type int version }
    TEXT_CHUNKS { int id PK int paper_id FK string chunk_id string content }
    USER_ACTIONS { int id PK int paper_id FK string user_id string action_type }
```

关键规则：`papers.arxiv_id`、`authors.normalized_name`、`parse_tasks.idempotency_key` 和结果版本组合唯一；`text_chunks` 只要求同一论文内 `chunk_id` 唯一；`user_actions` 不设置全表 `(user_id, paper_id)` 唯一约束。

## 后端组件图

```mermaid
flowchart LR
    Web[React/Vite 前端] --> API[FastAPI API]
    API --> Schema[Schema/DTO]
    API --> Service[Paper Service]
    Service --> Repo[Paper Repository]
    Repo --> ORM[SQLAlchemy Model]
    ORM --> DB[(SQLite/PostgreSQL)]
    Service --> Wiki[StructuredResult]
    Service --> QA[论文范围最小问答]
    Seed[python -m scripts.seed] --> Service
    Migration[Alembic] --> DB
```

## 检索时序

```mermaid
sequenceDiagram
    participant Web as React paperService
    participant API as GET /papers
    participant Service as PaperService
    participant Repo as PaperRepository
    participant DB as Database
    Web->>API: keyword, category, page, page_size
    API->>Service: validated filters
    Service->>Repo: list_papers(filters)
    Repo->>DB: count + filtered select
    DB-->>Repo: rows and total
    Repo-->>Service: Paper ORM objects
    Service-->>API: PaperPage DTO
    API-->>Web: {code, data, request_id}
```

## 当前接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/health` | API 与数据库健康检查 |
| `GET` | `/api/papers` | 关键词、作者、分类、时间范围、分页检索 |
| `POST` | `/api/papers/batch` | 按 `arxiv_id` 批量幂等写入论文和作者 |
| `GET` | `/api/papers/{paper_id}` | 数字 ID 读取数据库论文；字符串 ID 兼容 Pipeline 样例 |
| `GET` | `/api/papers/{paper_id}/wiki` | 读取数据库结构化结果；未生成时回退论文摘要 |
| `POST` | `/api/papers/{paper_id}/qa` | 数据库论文或 Pipeline 样例的可追溯问答 |

成功响应统一为 `{code: "OK", message: "", data: ..., request_id: "..."}`。前端开发环境默认通过 `/api` 代理到 `http://127.0.0.1:8000`，设置 `VITE_USE_MOCK=true` 可切回原型 Mock。

## 本地启动

```bash
cd SE26Project-04/backend
source .venv/bin/activate
python -m alembic upgrade head
python -m scripts.seed
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
