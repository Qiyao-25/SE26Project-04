import argparse
import json
import sys

from app.core.config import Settings
from app.core.database import create_engine_for
from app.main import create_app
from app.model import Base
from app.schema.common import ApiResponse
from app.service.health import get_health
from harness.scenarios import (
    dumps_result,
    run_agent_scenario,
    run_e2e_scenario,
    run_parse_scenario,
    run_qa_scenario,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m harness")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("health", help="检查 /health 业务响应")
    subparsers.add_parser("orm", help="列出 ORM 注册的表")
    for name, help_text in (
        ("agent", "验证结构化摘要和问答 Agent 契约"),
        ("parse", "验证本地论文解析、落库和图谱结果"),
        ("qa", "验证问答回答和引用校验"),
        ("e2e", "运行解析和问答完整验收场景"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument(
            "--live",
            action="store_true",
            help="调用当前环境配置的真实 LLM；默认使用确定性的 Harness Stub",
        )
    return parser


def run_health() -> int:
    settings = Settings(
        environment="test",
        database_url="sqlite:///:memory:",
        crawl_enabled=False,
        parse_scheduler_enabled=False,
    )
    app = create_app(settings)
    data = get_health(app.state.engine, settings)
    payload = ApiResponse(data=data, request_id="harness-health")
    print(json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if data.status == "ok" else 1


def run_orm() -> int:
    settings = Settings(environment="test", database_url="sqlite:///:memory:")
    engine = create_engine_for(settings)
    print(json.dumps({"tables": sorted(Base.metadata.tables), "dialect": engine.dialect.name}))
    return 0


def run_agent(command: str, *, live: bool) -> int:
    scenario = {
        "agent": run_agent_scenario,
        "parse": run_parse_scenario,
        "qa": run_qa_scenario,
        "e2e": run_e2e_scenario,
    }[command](live=live)
    print(dumps_result(scenario))
    return 0 if scenario.ok else 1


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "health":
        return run_health()
    if args.command == "orm":
        return run_orm()
    return run_agent(args.command, live=args.live)


if __name__ == "__main__":
    sys.exit(main())
