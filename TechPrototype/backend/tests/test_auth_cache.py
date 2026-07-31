from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, User
from app.schema.auth import RegisterRequest
from app.service.auth import invalidate_user_auth_cache, register, user_from_token


def test_auth_cache_reuses_verified_user_and_explicit_invalidation_restores_db_check(tmp_path: Path):
    settings = Settings(
        environment="dev",
        database_url=f"sqlite:///{tmp_path / 'auth-cache.db'}",
        auth_secret="cache-test-secret",
        auth_cache_ttl_s=60,
    )
    engine = create_engine_for(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        auth = register(session, RegisterRequest(email="cache@example.com", password="password123"), settings)

        assert user_from_token(session, auth.access_token, settings).email == "cache@example.com"
        user = session.get(User, int(auth.user.user_id))
        assert user is not None
        user.is_active = False
        session.commit()

        # The short cache removes repeated reads during normal authenticated traffic.
        assert user_from_token(session, auth.access_token, settings).email == "cache@example.com"
        invalidate_user_auth_cache(user.id)

        try:
            user_from_token(session, auth.access_token, settings)
        except ValueError as exc:
            assert str(exc) == "AUTH_INVALID"
        else:
            raise AssertionError("invalidated cache must not accept a disabled user")
