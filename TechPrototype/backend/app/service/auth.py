import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.model import User
from app.schema.auth import AccountUpdate, AuthResponse, AuthUser, LoginRequest, RegisterRequest


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ITERATIONS = 120_000
TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60


def _normalize_email(value: str) -> str:
    email = value.strip().casefold()
    if not EMAIL_PATTERN.match(email) and email != "admin":
        raise ValueError("EMAIL_INVALID")
    return email


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS).hex()
    return f"{ITERATIONS}${salt.hex()}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        iterations, salt_hex, expected = stored.split("$", 2)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _user_data(user: User) -> AuthUser:
    return AuthUser(user_id=str(user.id), email=user.email, role=user.role)


def _token(user: User, settings: Settings) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.auth_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{signature}"


def _response(user: User, settings: Settings) -> AuthResponse:
    return AuthResponse(access_token=_token(user, settings), user=_user_data(user))


def register(session: Session, payload: RegisterRequest, settings: Settings) -> AuthResponse:
    email = _normalize_email(payload.email)
    if session.scalar(select(User).where(User.email == email)) is not None:
        raise ValueError("EMAIL_EXISTS")
    user = User(email=email, password_hash=hash_password(payload.password), role="user")
    session.add(user)
    session.commit()
    session.refresh(user)
    return _response(user, settings)


def login(session: Session, payload: LoginRequest, settings: Settings) -> AuthResponse:
    email = _normalize_email(payload.email)
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise ValueError("AUTH_INVALID")
    user.last_login_at = datetime.now(timezone.utc)
    session.commit()
    return _response(user, settings)


def user_from_token(session: Session, token: str, settings: Settings) -> AuthUser:
    try:
        raw, signature = token.split(".", 1)
        expected = hmac.new(settings.auth_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        padded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if int(payload["exp"]) < int(time.time()):
            raise ValueError
        user = session.get(User, int(payload["sub"]))
        if user is None or not user.is_active:
            raise ValueError
        return _user_data(user)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError("AUTH_INVALID")


def update_account(session: Session, user_id: str, payload: AccountUpdate, settings: Settings) -> AuthResponse:
    user = session.get(User, int(user_id))
    if user is None or not user.is_active:
        raise ValueError("AUTH_INVALID")
    if payload.password and (not payload.current_password or not verify_password(payload.current_password, user.password_hash)):
        raise ValueError("PASSWORD_INVALID")
    if payload.email:
        email = _normalize_email(payload.email)
        existing = session.scalar(select(User).where(User.email == email, User.id != user.id))
        if existing is not None:
            raise ValueError("EMAIL_EXISTS")
        user.email = email
    if payload.password:
        user.password_hash = hash_password(payload.password)
    user.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(user)
    return _response(user, settings)
