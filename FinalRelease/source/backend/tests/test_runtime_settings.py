"""Unit tests for runtime settings persistence."""

import json

from app.core.config import Settings
from app.service.runtime_settings import (
    apply_runtime_settings,
    load_runtime_settings,
    runtime_settings_path,
    save_runtime_settings,
    update_crawl_settings,
)


def test_runtime_settings_load_save_roundtrip(tmp_path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 'runtime.db').as_posix()}",
        crawl_enabled=False,
        crawl_interval_s=3600,
    )
    assert load_runtime_settings(settings) == {}
    saved = save_runtime_settings(settings, {"crawl_enabled": True, "crawl_interval_s": 7200})
    assert saved["crawl_enabled"] is True
    assert saved["crawl_interval_s"] == 7200
    assert runtime_settings_path(settings).exists()
    reloaded = load_runtime_settings(settings)
    assert reloaded["crawl_enabled"] is True
    applied = apply_runtime_settings(settings)
    assert applied["crawl_enabled"] is True
    assert applied["crawl_interval_s"] >= 7200
    updated = update_crawl_settings(settings, crawl_enabled=False, crawl_interval_s=1800)
    assert updated["crawl_enabled"] is False
    assert updated["crawl_interval_s"] >= 1800


def test_runtime_settings_invalid_json(tmp_path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{(tmp_path / 'bad.db').as_posix()}")
    path = runtime_settings_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert load_runtime_settings(settings) == {}
    path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    assert load_runtime_settings(settings) == {}


def test_runtime_settings_non_sqlite_data_dir(tmp_path) -> None:
    settings = Settings(
        environment="test",
        database_url="postgresql://localhost/papermate",
        paper_storage_dir=str(tmp_path / "relative" / "pdfs"),
    )
    path = runtime_settings_path(settings)
    assert path.parent == tmp_path / "relative"
    assert path.name == "runtime_settings.json"
