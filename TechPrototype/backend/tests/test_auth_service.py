"""Unit tests for auth service edge cases."""

import base64
import hashlib
import hmac
import json
import time

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import create_engine_for
from app.model import Base, User
from app.schema.auth import AccountUpdate, RegisterRequest
from app.service.auth import (
    _normalize_email,
    hash_password,
    register,
    update_account,
    user_from_token,
    verify_password,
)


def _session(tmp_path) -> Session:
    engine = create_engine_for(
        Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'auth-svc.db'}", auth_secret="test-secret")
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_normalize_email_and_verify_password() -> None:
    assert _normalize_email("  Reader@Example.COM ") == "reader@example.com"
    assert _normalize_email("admin") == "admin"
    with pytest.raises(ValueError, match="EMAIL_INVALID"):
        _normalize_email("not-an-email")
    stored = hash_password("password123")
    assert verify_password("password123", stored) is True
    assert verify_password("wrong", stored) is False
    assert verify_password("password123", "bad-format") is False


def test_user_from_token_expired_tampered_inactive(tmp_path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'auth-svc.db'}", auth_secret="test-secret")
    with _session(tmp_path) as session:
        registered = register(session, RegisterRequest(email="tok@example.com", password="password123"), settings)
        user = user_from_token(session, registered.access_token, settings)
        assert user.email == "tok@example.com"

        raw, sig = registered.access_token.split(".", 1)
        tampered = f"{raw}x.{sig}"
        with pytest.raises(ValueError, match="AUTH_INVALID"):
            user_from_token(session, tampered, settings)

        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode())
        payload["exp"] = int(time.time()) - 10
        expired_raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
        expired_sig = hmac.new(settings.auth_secret.encode(), expired_raw.encode(), hashlib.sha256).hexdigest()
        with pytest.raises(ValueError, match="AUTH_INVALID"):
            user_from_token(session, f"{expired_raw}.{expired_sig}", settings)

        db_user = session.get(User, int(user.user_id))
        assert db_user is not None
        db_user.is_active = False
        session.commit()
        with pytest.raises(ValueError, match="AUTH_INVALID"):
            user_from_token(session, registered.access_token, settings)


def test_register_duplicate_and_update_account_branches(tmp_path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'auth-svc.db'}", auth_secret="test-secret")
    with _session(tmp_path) as session:
        register(session, RegisterRequest(email="dup@example.com", password="password123"), settings)
        with pytest.raises(ValueError, match="EMAIL_EXISTS"):
            register(session, RegisterRequest(email="dup@example.com", password="other123"), settings)

        auth = register(session, RegisterRequest(email="change@example.com", password="password123"), settings)
        with pytest.raises(ValueError, match="PASSWORD_INVALID"):
            update_account(
                session,
                auth.user.user_id,
                AccountUpdate(password="newpass123"),
                settings,
            )

        updated = update_account(
            session,
            auth.user.user_id,
            AccountUpdate(current_password="password123", password="newpass123"),
            settings,
        )
        assert updated.access_token != auth.access_token

        register(session, RegisterRequest(email="other@example.com", password="password123"), settings)
        with pytest.raises(ValueError, match="EMAIL_EXISTS"):
            update_account(
                session,
                auth.user.user_id,
                AccountUpdate(email="other@example.com"),
                settings,
            )

        email_changed = update_account(
            session,
            auth.user.user_id,
            AccountUpdate(email="renamed@example.com"),
            settings,
        )
        assert email_changed.user.email == "renamed@example.com"
