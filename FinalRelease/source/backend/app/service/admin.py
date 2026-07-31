from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.runtime import format_uptime, process_started_at, uptime_seconds
from app.model import ParseTask, Paper, User, UserAction, UserProfile
from app.service.tasks import MAX_ATTEMPTS


def explain_parse_failure(*, error_code: str | None, stage: str | None, status: str | None) -> dict:
    """Map raw task failure into multi-agent stage + human-readable reason."""
    code = (error_code or "").upper()
    stage_key = (stage or "").lower()
    status_key = (status or "").lower()

    if code in {"CONTENT_EMPTY", "PARSE_FAILED"} or stage_key == "fetch":
        return {
            "agent": "抓取 Agent",
            "stage_label": "抓取 / 正文提取",
            "reason": "未能从 PDF 或 HTML 获得可用正文，抓取环节判定内容为空或不可解析。",
        }
    if code == "PAPER_NOT_FOUND":
        return {
            "agent": "抓取 Agent",
            "stage_label": "抓取 / 入库校验",
            "reason": "任务关联的论文记录不存在或已被删除。",
        }
    if code == "STALE_TASK" or status_key == "timed_out":
        return {
            "agent": "调度器",
            "stage_label": "任务调度",
            "reason": "解析任务长时间未完成，已被超时回收。",
        }
    if code == "SUPERSEDED":
        return {
            "agent": "调度器",
            "stage_label": "任务调度",
            "reason": "该任务被更新的强制解析请求取代。",
        }
    if stage_key in {"summarize", "parse"}:
        return {
            "agent": "摘要 Agent",
            "stage_label": "结构化摘要",
            "reason": "摘要 Agent 在生成 summary / concepts / methods 时失败。",
        }
    if stage_key == "validate":
        return {
            "agent": "校验 Agent",
            "stage_label": "内容校验",
            "reason": "校验 Agent 处理结构化结果时出现异常。",
        }
    if stage_key == "graph":
        return {
            "agent": "图谱 Agent",
            "stage_label": "知识图谱",
            "reason": "图谱 Agent 构建主题 / 概念关联时失败。",
        }
    if stage_key == "persist":
        return {
            "agent": "持久化",
            "stage_label": "结果落库",
            "reason": "解析结果写入数据库或文本块时失败。",
        }
    if code == "WORKER_ERROR":
        return {
            "agent": "解析流水线",
            "stage_label": stage_key or "未知阶段",
            "reason": "流水线执行过程中发生未捕获异常（任务崩溃），已记录为 WORKER_ERROR。",
        }
    return {
        "agent": "解析流水线",
        "stage_label": stage_key or "未知阶段",
        "reason": f"解析失败（{code or 'UNKNOWN'}）。",
    }


def admin_overview(session: Session, settings: Settings, *, started_at=None) -> dict:
    task_counts = {
        status: session.scalar(select(func.count(ParseTask.id)).where(ParseTask.status == status)) or 0
        for status in ("queued", "running", "succeeded", "failed", "timed_out")
    }
    start = started_at or process_started_at()
    seconds = uptime_seconds(start)
    return {
        "metrics": {
            "papers": session.scalar(select(func.count(Paper.id)).where(Paper.deleted_at.is_(None))) or 0,
            "users": session.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0,
            "qa_ready": session.scalar(select(func.count(Paper.id)).where(Paper.ingest_status == "qa_ready")) or 0,
            "tasks": sum(task_counts.values()),
            "uptime_seconds": seconds,
            "uptime": format_uptime(seconds),
            "started_at": start.isoformat() if start is not None else None,
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
        explained = explain_parse_failure(error_code=task.error_code, stage=task.stage, status=task.status)
        exceptions.append({
            "paper": task.paper_id,
            "task_id": task.id,
            "title": paper.title if paper else f"paper-{task.paper_id}",
            "detail": explained["reason"],
            "error_code": task.error_code,
            "agent": explained["agent"],
            "stage_label": explained["stage_label"],
            "type": task.stage or "parse",
            "status": task.status,
            "attempt": task.attempt,
            "retryable": task.status in {"failed", "timed_out"} and task.attempt < MAX_ATTEMPTS,
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
