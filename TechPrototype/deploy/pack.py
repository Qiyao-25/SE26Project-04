#!/usr/bin/env python3
"""Build deployable packages for PaperMate (frontend dist + backend source bundle).

Usage (from repo root):
  python TechPrototype/deploy/pack.py
  python TechPrototype/deploy/pack.py --out dist/packages
  # 中间产物建议输出到 ppp 工作区：
  python TechPrototype/deploy/pack.py --out ../ppp/deploy-artifacts/packages

Outputs:
  papermate-frontend-<version>.tar.gz   # Vite dist + README
  papermate-backend-<version>.tar.gz    # backend app (no .venv / .env secrets)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

TECH_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TECH_ROOT.parent
FRONTEND = REPO_ROOT / "UIPrototype" / "frontend"
BACKEND = TECH_ROOT / "backend"
DEFAULT_OUT = REPO_ROOT / "dist" / "packages"

BACKEND_EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".pytest_cache", "data", ".mypy_cache", "papermate_backend.egg-info"}
BACKEND_EXCLUDE_FILES = {".env", ".env.local"}


def _version() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd), f"(cwd={cwd})")
    subprocess.run(cmd, cwd=cwd, check=True)


def build_frontend(stage: Path) -> None:
    env_prod = FRONTEND / ".env.production"
    example = TECH_ROOT / "deploy" / "env.frontend.production.example"
    if not env_prod.exists() and example.exists():
        shutil.copy2(example, env_prod)
        print(f"created {env_prod} from example")
    _run(["npm", "ci"], FRONTEND) if (FRONTEND / "package-lock.json").exists() else _run(["npm", "install"], FRONTEND)
    _run(["npm", "run", "build"], FRONTEND)
    dist = FRONTEND / "dist"
    if not dist.exists():
        raise SystemExit("frontend dist not found after build")
    target = stage / "frontend"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(dist, target)
    readme = target / "README.txt"
    readme.write_text(
        "PaperMate 前端静态包\n"
        "1. 解压/复制到 Nginx root，例如 /var/www/papermate/\n"
        "2. 使用 deploy/nginx.papermate.conf.example 配置 /api 反代\n"
        "3. 构建时 VITE_API_BASE_URL=/api，VITE_USE_MOCK=false\n",
        encoding="utf-8",
    )


def stage_backend(stage: Path) -> None:
    target = stage / "backend"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    def ignore(directory: str, names: list[str]) -> set[str]:
        skipped: set[str] = set()
        for name in names:
            path = Path(directory) / name
            if name in BACKEND_EXCLUDE_DIRS and path.is_dir():
                skipped.add(name)
            if name in BACKEND_EXCLUDE_FILES and path.is_file():
                skipped.add(name)
            if name.endswith(".pyc"):
                skipped.add(name)
        return skipped

    for item in BACKEND.iterdir():
        if item.name in BACKEND_EXCLUDE_DIRS or item.name in BACKEND_EXCLUDE_FILES:
            continue
        dest = target / item.name
        if item.is_dir():
            shutil.copytree(item, dest, ignore=ignore)
        else:
            shutil.copy2(item, dest)

    # Ship production env template (not secrets)
    shutil.copy2(TECH_ROOT / "deploy" / "env.backend.production.example", target / ".env.production.example")
    (target / "README.txt").write_text(
        "PaperMate 后端安装包\n"
        "1. 解压到 /opt/papermate/backend\n"
        "2. python3 -m venv .venv && .venv/bin/pip install -e '.[postgres]'\n"
        "3. 复制 .env.production.example 为 .env 并填写密钥\n"
        "4. .venv/bin/python -m alembic upgrade head\n"
        "5. 可选导入种子：.venv/bin/python -m scripts.import_seed --seed /path/to/seed.json\n"
        "6. 使用 deploy/papermate-backend.service.example 配置 systemd\n",
        encoding="utf-8",
    )


def _tar(src_dir: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(src_dir, arcname=src_dir.name)
    print(f"wrote {archive}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack PaperMate deploy packages")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--skip-frontend-build", action="store_true")
    parser.add_argument("--version", default=_version())
    args = parser.parse_args()

    stage = args.out / "_stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    if not args.skip_frontend_build:
        build_frontend(stage)
    else:
        dist = FRONTEND / "dist"
        if not dist.exists():
            raise SystemExit("--skip-frontend-build requires existing UIPrototype/frontend/dist")
        shutil.copytree(dist, stage / "frontend")

    stage_backend(stage)
    shutil.copytree(TECH_ROOT / "deploy", stage / "deploy", dirs_exist_ok=True)

    version = args.version
    _tar(stage / "frontend", args.out / f"papermate-frontend-{version}.tar.gz")
    _tar(stage / "backend", args.out / f"papermate-backend-{version}.tar.gz")
    # Optional third package: deploy configs + docs
    deploy_bundle = stage / "deploy-bundle"
    deploy_bundle.mkdir()
    for name in ("nginx.papermate.conf.example", "papermate-backend.service.example",
                 "env.backend.production.example", "env.frontend.production.example"):
        shutil.copy2(TECH_ROOT / "deploy" / name, deploy_bundle / name)
    docs = TECH_ROOT / "docs" / "部署说明.md"
    if docs.exists():
        shutil.copy2(docs, deploy_bundle / "部署说明.md")
    _tar(deploy_bundle, args.out / f"papermate-deploy-config-{version}.tar.gz")

    print("\nPackages ready:")
    for path in sorted(args.out.glob(f"papermate-*-{version}.tar.gz")):
        print(" -", path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"command failed: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode)
