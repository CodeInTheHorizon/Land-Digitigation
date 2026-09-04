"""JWT token management and password hashing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str,
    extra: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expire, "type": "access"}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    # Derive a separate signing key for refresh tokens so a leaked refresh
    # token cannot be trivially edited into an access token.
    refresh_key = settings.JWT_SECRET_KEY + ":refresh"
    return jwt.encode(payload, refresh_key, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, *, token_type: str = "access") -> Optional[dict[str, Any]]:
    """Decode and validate a JWT. Returns payload dict or None on failure.

    Parameters
    ----------
    token_type : str
        ``"access"`` or ``"refresh"`` — selects the signing key.
    """
    key = settings.JWT_SECRET_KEY
    if token_type == "refresh":
        key = key + ":refresh"
    try:
        payload = jwt.decode(token, key, algorithms=[settings.JWT_ALGORITHM])
        # Enforce token type matches
        if payload.get("type") != token_type:
            return None
        return payload
    except JWTError:
        return None
