"""Authentication, password hashing and access control.

Spec section 49. Three decisions worth stating:

**Argon2id for passwords.** It is the current recommendation and it is memory-
hard, which is what makes a stolen hash table expensive rather than merely
slow. Parameters are the argon2-cffi defaults, which track the RFC 9106
guidance, and the hash string records them so a future parameter change can
re-hash on next login rather than invalidating every password.

**JWT for sessions, short-lived.** A token is a bearer credential: anyone
holding it is the user. So it expires in hours, it carries no personal data
beyond the subject and role, and the signing secret must be supplied — the
service refuses to start in production without one rather than falling back to
a default that would be identical on every deployment on earth.

**Authorisation is not done here.** A valid token proves who you are, not what
you may see. Every repository read is scoped by the requesting user, so a
project belonging to someone else is not found rather than forbidden — a 404
does not confirm that the id exists.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.base import get_session
from .db.models import User

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 12

_hasher = PasswordHasher()

#: Roles in ascending order of privilege.
ROLE_ORDER = ("guest", "free", "professional", "engineer", "admin")

#: The minimum password length. Length beats complexity rules; a 12-character
#: passphrase resists guessing better than "P@ss1!" and people can remember it.
MIN_PASSWORD_LENGTH = 12


class WeakPassword(ValueError):
    pass


def jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if secret:
        return secret
    if os.environ.get("GEOFATALI_ENV") == "production":
        raise RuntimeError(
            "JWT_SECRET is not set. Refusing to start in production with a default "
            "signing key — every deployment would share it and anyone could mint a "
            "token for any user."
        )
    return "development-only-do-not-use-in-production"


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPassword(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters. A long "
            "passphrase is both easier to remember and harder to guess than a short "
            "password with symbols in it."
        )
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the stored hash used weaker parameters than we now use."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def create_token(user_id: uuid.UUID, role: str, *, ttl_hours: int = TOKEN_TTL_HOURS) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM])


@dataclass(frozen=True)
class Principal:
    """Who is making this request."""

    id: uuid.UUID
    email: str
    role: str
    organization_id: uuid.UUID | None
    registration_no: str | None

    def at_least(self, role: str) -> bool:
        return ROLE_ORDER.index(self.role) >= ROLE_ORDER.index(role)


_bearer = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sign in to continue.",
    headers={"WWW-Authenticate": "Bearer"},
)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> Principal:
    if credentials is None:
        raise _UNAUTHENTICATED
    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise _UNAUTHENTICATED from exc

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise _UNAUTHENTICATED from exc

    # The role is read from the database, never from the token: a user demoted
    # five minutes ago must not keep engineer rights until their token expires.
    user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise _UNAUTHENTICATED
    return Principal(
        id=user.id,
        email=user.email,
        role=user.role,
        organization_id=user.organization_id,
        registration_no=user.registration_no,
    )


def require_role(minimum: str):
    """Dependency factory: refuse anyone below ``minimum``."""
    if minimum not in ROLE_ORDER:
        raise ValueError(f"Unknown role {minimum!r}")

    def dependency(principal: Principal = Depends(current_user)) -> Principal:
        if not principal.at_least(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires the {minimum} role or above.",
            )
        return principal

    return dependency
