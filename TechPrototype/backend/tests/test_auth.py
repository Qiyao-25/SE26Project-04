from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base
from app.schema.auth import LoginRequest, RegisterRequest
from app.service.auth import login, register, user_from_token


def test_register_login_and_token_roundtrip(tmp_path: Path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'auth.db'}", auth_secret="test-secret")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        registered = register(session, RegisterRequest(email="reader@example.com", password="password123"), settings)
        assert registered.user.email == "reader@example.com"
        logged_in = login(session, LoginRequest(email="reader@example.com", password="password123"), settings)
        current = user_from_token(session, logged_in.access_token, settings)
        assert current.user_id == logged_in.user.user_id
        assert current.role == "user"


def test_login_rejects_wrong_password(tmp_path: Path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'auth-invalid.db'}")
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        register(session, RegisterRequest(email="reader@example.com", password="password123"), settings)
        try:
            login(session, LoginRequest(email="reader@example.com", password="wrong123"), settings)
        except ValueError as exc:
            assert str(exc) == "AUTH_INVALID"
        else:
            raise AssertionError("expected AUTH_INVALID")
