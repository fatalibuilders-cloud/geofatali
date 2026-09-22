"""Users and registration."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import User
from ..security import hash_password, needs_rehash, verify_password
from . import Conflict, NotFound


def normalise_email(email: str) -> str:
    return email.strip().lower()


def create_user(
    session: Session,
    *,
    email: str,
    password: str,
    name: str | None = None,
    role: str = "free",
    registration_no: str | None = None,
) -> User:
    if role == "engineer" and not registration_no:
        raise Conflict(
            "An engineer account needs a board registration number. Reviews signed "
            "by this account will carry it, and a signature without one is worthless."
        )
    user = User(
        email=normalise_email(email),
        password_hash=hash_password(password),
        name=name,
        role=role,
        registration_no=registration_no,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("An account already exists for that email address.") from exc
    return user


def by_email(session: Session, email: str) -> User | None:
    return session.execute(
        select(User).where(User.email == normalise_email(email))
    ).scalar_one_or_none()


def by_id(session: Session, user_id: uuid.UUID) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFound(f"No user {user_id}")
    return user


def authenticate(session: Session, *, email: str, password: str) -> User | None:
    """Return the user for correct credentials, otherwise None.

    The same amount of work is done whether or not the email exists, so the
    response time does not reveal which accounts are registered.
    """
    user = by_email(session, email)
    if user is None:
        # Verify against a throwaway hash so a missing account costs the same
        # as a wrong password.
        verify_password(
            "$argon2id$v=19$m=65536,t=3,p=4$" + "A" * 22 + "$" + "B" * 43, password
        )
        return None
    if not verify_password(user.password_hash, password):
        return None
    if needs_rehash(user.password_hash):
        # Silently upgrade to current parameters while we have the plaintext.
        user.password_hash = hash_password(password)
        session.flush()
    return user
