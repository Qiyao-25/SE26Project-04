from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.tasks import require_worker_access
from app.core.config import Settings


def request_for(settings: Settings):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings)))


def test_dev_worker_auth_is_optional_without_token() -> None:
    require_worker_access(request_for(Settings(environment="dev")), None)
    require_worker_access(
        request_for(Settings(environment="dev", worker_token="replace-with-local-worker-token")),
        None,
    )


def test_production_worker_auth_requires_matching_token() -> None:
    request = request_for(Settings(environment="prod", worker_token="production-secret"))
    with pytest.raises(HTTPException) as missing:
        require_worker_access(request, None)
    assert missing.value.status_code == 403

    with pytest.raises(HTTPException):
        require_worker_access(request, "wrong-secret")

    require_worker_access(request, "production-secret")
