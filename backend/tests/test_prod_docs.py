from app.core.config import Settings, validate_production_settings
from app.main import create_app


def test_prod_disables_docs_by_default() -> None:
    settings = Settings(
        environment="prod",
        database_url="sqlite:///:memory:",
        enable_docs=None,
        auth_secret="prod-strong-secret-value-32chars",
        worker_token="prod-strong-worker-token-32chars",
        cors_origins="https://example.com",
    )
    assert settings.enable_docs is False
    app = create_app(settings)
    assert app.docs_url is None
    assert app.openapi_url is None


def test_prod_rejects_default_auth_secret() -> None:
    settings = Settings(environment="prod", database_url="sqlite:///:memory:", enable_docs=None)
    try:
        create_app(settings)
    except RuntimeError as exc:
        assert "PAPERMATE_AUTH_SECRET" in str(exc)
    else:
        raise AssertionError("production must reject the development auth secret")


def test_dev_keeps_docs() -> None:
    settings = Settings(environment="dev", database_url="sqlite:///:memory:")
    assert settings.enable_docs is True
    app = create_app(settings)
    assert app.docs_url == "/docs"


def test_prod_rejects_weak_auth_secret() -> None:
    settings = Settings(
        environment="prod",
        database_url="sqlite:///:memory:",
        auth_secret="papermate-dev-secret",
        worker_token="prod-strong-worker-token-32chars",
        cors_origins="https://example.com",
    )
    try:
        validate_production_settings(settings)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "AUTH_SECRET" in str(exc)
