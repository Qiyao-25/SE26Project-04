from app.core.config import Settings
from app.main import create_app


def test_prod_disables_docs_by_default() -> None:
    settings = Settings(environment="prod", database_url="sqlite:///:memory:", enable_docs=None)
    assert settings.enable_docs is False
    app = create_app(settings)
    assert app.docs_url is None
    assert app.openapi_url is None


def test_dev_keeps_docs() -> None:
    settings = Settings(environment="dev", database_url="sqlite:///:memory:")
    assert settings.enable_docs is True
    app = create_app(settings)
    assert app.docs_url == "/docs"
