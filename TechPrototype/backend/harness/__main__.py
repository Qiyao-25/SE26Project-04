import argparse
import json
import sys

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import create_engine_for
from app.main import create_app
from app.model import Base


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m harness")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("health", help="通过 FastAPI 测试客户端检查 /health")
    subparsers.add_parser("orm", help="列出 ORM 注册的表")
    return parser


def run_health() -> int:
    settings = Settings(environment="test", database_url="sqlite:///:memory:")
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "harness-health"})
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    return 0 if response.status_code == 200 and response.json()["code"] == "OK" else 1


def run_orm() -> int:
    settings = Settings(environment="test", database_url="sqlite:///:memory:")
    engine = create_engine_for(settings)
    print(json.dumps({"tables": sorted(Base.metadata.tables), "dialect": engine.dialect.name}))
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return run_health() if args.command == "health" else run_orm()


if __name__ == "__main__":
    sys.exit(main())

