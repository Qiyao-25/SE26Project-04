from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.model import ParseTask, Paper, User, UserAction, UserProfile


def admin_overview(session: Session, settings: Settings) -> dict:
    task_counts = {
        status: session.scalar(select(func.count(ParseTask.id)).where(ParseTask.status == status)) or 0
        for status in ("queued", "running", "succeeded", "failed", "timed_out")
    }
    return {
        "metrics": {
            "papers": session.scalar(select(func.count(Paper.id)).where(Paper.deleted_at.is_(None))) or 0,
            "users": session.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0,
            "qa_ready": session.scalar(select(func.count(Paper.id)).where(Paper.ingest_status == "qa_ready")) or 0,
            "tasks": sum(task_counts.values()),
        },
        "task_counts": task_counts,
        "agents": [
            {"id": "crawl", "name": "抓取调度", "ready": True, "status": "订阅同步 / 定时入库", "role": "ingest"},
            {"id": "parse", "name": "摘要 Agent", "ready": settings.parse_agent_ready, "status": "可用" if settings.parse_agent_ready else "降级模式", "role": "summarize"},
            {"id": "validate", "name": "校验 Agent", "ready": True, "status": "规则校验 Wiki 完整性", "role": "validate"},
            {"id": "graph", "name": "图谱 Agent", "ready": settings.graph_agent_ready, "status": "可用" if settings.graph_agent_ready else "启发式图谱", "role": "graph"},
            {"id": "qa", "name": "问答 Agent", "ready": settings.qa_agent_ready, "status": "可用" if settings.qa_agent_ready else "未配置", "role": "qa"},
            {"id": "search", "name": "检索 Agent", "ready": settings.search_agent_ready, "status": "可用" if settings.search_agent_ready else "规则检索", "role": "search"},
            {"id": "assist", "name": "阅读 Agent", "ready": settings.assist_agent_ready, "status": "可用" if settings.assist_agent_ready else "模板回退", "role": "assist"},
            {"id": "compare", "name": "对比 Agent", "ready": settings.assist_agent_ready, "status": "可用" if settings.assist_agent_ready else "模板回退", "role": "compare"},
        ],
        "pipeline": [
            {"stage": "fetch", "agent": "抓取/正文提取", "description": "拉取 PDF/HTML 或摘要"},
            {"stage": "summarize", "agent": "摘要 Agent", "description": "生成 summary / concepts / methods"},
            {"stage": "validate", "agent": "校验 Agent", "description": "完整性与不确定字段标记"},
            {"stage": "graph", "agent": "图谱 Agent", "description": "主题/概念关联与脉络"},
            {"stage": "persist", "agent": "持久化", "description": "写入 Wiki 结构化结果与文本块"},
        ],
    }


def admin_tasks(session: Session, limit: int = 50) -> list[dict]:
    rows = session.scalars(select(ParseTask).order_by(ParseTask.requested_at.desc()).limit(limit)).all()
    output = []
    for task in rows:
        paper = session.get(Paper, task.paper_id)
        stage_progress = {"fetch": 15, "parse": 35, "summarize": 60, "graph": 75, "persist": 90, "completed": 100, "failed": 100}
        output.append({
            "id": task.id,
            "paper_id": task.paper_id,
            "title": paper.title if paper else f"paper-{task.paper_id}",
            "status": task.status,
            "stage": task.stage or "queued",
            "progress": stage_progress.get(task.stage or "queued", 0),
            "error_code": task.error_code,
            "requested_at": task.requested_at,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
        })
    return output


def admin_users(session: Session, limit: int = 100) -> list[dict]:
    rows = session.scalars(select(User).order_by(User.created_at.desc()).limit(limit)).all()
    return [{
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "status": "启用" if user.is_active else "禁用",
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    } for user in rows]


def update_user_status(session: Session, user_id: int, is_active: bool) -> dict:
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("USER_NOT_FOUND")
    if user.role == "admin" and not is_active:
        raise ValueError("ADMIN_CANNOT_DISABLE")
    user.is_active = is_active
    session.commit()
    session.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "status": "启用" if user.is_active else "禁用",
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


def delete_user(session: Session, user_id: int) -> dict:
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("USER_NOT_FOUND")
    if user.role == "admin":
        raise ValueError("ADMIN_CANNOT_DELETE")
    email = user.email
    uid = str(user.id)
    for action in session.scalars(select(UserAction).where(UserAction.user_id == uid)).all():
        session.delete(action)
    profile = session.get(UserProfile, uid)
    if profile is not None:
        session.delete(profile)
    session.delete(user)
    session.commit()
    return {"deleted": True, "id": user_id, "email": email}


def admin_quality(session: Session, limit: int = 50) -> dict:
    failed = session.scalars(
        select(ParseTask).where(ParseTask.status.in_(("failed", "timed_out"))).order_by(ParseTask.requested_at.desc()).limit(limit)
    ).all()
    exceptions = []
    for task in failed:
        paper = session.get(Paper, task.paper_id)
        if paper is not None and paper.deleted_at is not None:
            continue
        exceptions.append({
            "paper": task.paper_id,
            "task_id": task.id,
            "title": paper.title if paper else f"paper-{task.paper_id}",
            "detail": task.error_code or "解析任务失败",
            "type": task.stage or "parse",
            "status": task.status,
            "attempt": task.attempt,
            "retryable": task.status in {"failed", "timed_out"} and task.attempt < 3,
            "time": task.finished_at or task.requested_at,
        })
    total = session.scalar(select(func.count(ParseTask.id))) or 0
    failed_total = session.scalar(
        select(func.count(ParseTask.id)).where(ParseTask.status.in_(("failed", "timed_out")))
    ) or 0
    pending = session.scalar(
        select(func.count(Paper.id)).where(
            Paper.deleted_at.is_(None),
            Paper.ingest_status.in_(("metadata_only", "downloaded")),
        )
    ) or 0
    queued = session.scalar(select(func.count(ParseTask.id)).where(ParseTask.status == "queued")) or 0
    running = session.scalar(select(func.count(ParseTask.id)).where(ParseTask.status == "running")) or 0
    fetch_failed = session.scalar(
        select(func.count(ParseTask.id)).where(
            ParseTask.status.in_(("failed", "timed_out")),
            ParseTask.stage == "fetch",
        )
    ) or 0
    summarize_failed = session.scalar(
        select(func.count(ParseTask.id)).where(
            ParseTask.status.in_(("failed", "timed_out")),
            ParseTask.stage.in_(("summarize", "parse", "persist")),
        )
    ) or 0
    return {
        "exceptions": exceptions,
        "rates": {
            "抓取": round((fetch_failed / total) * 100, 2) if total else 0,
            "摘要": round((summarize_failed / total) * 100, 2) if total else 0,
            "失败占比": round((failed_total / total) * 100, 2) if total else 0,
        },
        "queue": {
            "pending_papers": pending,
            "queued_tasks": queued,
            "running_tasks": running,
            "failed_tasks": failed_total,
        },
    }


def admin_audit(session: Session, limit: int = 50) -> list[dict]:
    rows = session.scalars(select(ParseTask).order_by(ParseTask.requested_at.desc()).limit(limit)).all()
    return [{
        "user": "system",
        "time": task.requested_at,
        "type": "解析任务",
        "detail": f"论文 #{task.paper_id} · {task.status}",
        "level": "Error" if task.status in {"failed", "timed_out"} else "Info",
    } for task in rows]
