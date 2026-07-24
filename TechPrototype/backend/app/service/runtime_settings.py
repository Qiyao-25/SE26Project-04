"""Persist runtime overrides (admin crawl schedule) under the data directory."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("papermate.runtime_settings")


def data_dir_for(settings) -> Path:
    url = str(getattr(settings, "database_url", "") or "")
    if url.startswith("sqlite:///"):
        raw = url.removeprefix("sqlite:///")
        db_path = Path(raw)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        return db_path.parent
    storage = Path(getattr(settings, "paper_storage_dir", "data/pdfs"))
    if not storage.is_absolute():
        storage = Path.cwd() / storage
    return storage.parent


def runtime_settings_path(settings) -> Path:
    return data_dir_for(settings) / "runtime_settings.json"


def load_runtime_settings(settings) -> dict[str, Any]:
    path = runtime_settings_path(settings)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("runtime_settings_load_failed path=%s err=%s", path, exc)
        return {}


def save_runtime_settings(settings, patch: dict[str, Any]) -> dict[str, Any]:
    path = runtime_settings_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = load_runtime_settings(settings)
    current.update({key: value for key, value in patch.items() if value is not None})
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current


def apply_runtime_settings(settings) -> dict[str, Any]:
    data = load_runtime_settings(settings)
    if "crawl_interval_s" in data:
        try:
            settings.crawl_interval_s = max(60, int(data["crawl_interval_s"]))
        except (TypeError, ValueError):
            pass
    if "crawl_enabled" in data:
        settings.crawl_enabled = bool(data["crawl_enabled"])
    return {
        "crawl_enabled": bool(settings.crawl_enabled),
        "crawl_interval_s": max(60, int(settings.crawl_interval_s)),
    }


def update_crawl_settings(settings, *, crawl_enabled: bool | None = None, crawl_interval_s: int | None = None) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if crawl_enabled is not None:
        settings.crawl_enabled = bool(crawl_enabled)
        patch["crawl_enabled"] = settings.crawl_enabled
    if crawl_interval_s is not None:
        settings.crawl_interval_s = max(60, int(crawl_interval_s))
        patch["crawl_interval_s"] = settings.crawl_interval_s
    if patch:
        save_runtime_settings(settings, patch)
    return {
        "crawl_enabled": bool(settings.crawl_enabled),
        "crawl_interval_s": max(60, int(settings.crawl_interval_s)),
    }
