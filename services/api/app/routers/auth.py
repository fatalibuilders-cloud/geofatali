"""Registration, sign-in and the current account."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..api_models import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from ..db.base import get_session
from ..repositories import Conflict, audit, users
from ..security import TOKEN_TTL_HOURS, Principal, WeakPassword, create_token, current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, session: Session = Depends(get_session)) -> TokenResponse:
    """Create an account.

    The role is constrained by the request model to `free` or `professional`.
    An engineer account — the only one that can approve an assessment — is
    granted by an administrator against a verified board registration, never
    claimed by the person signing up.
    """
    try:
        user = users.create_user(
            session,
            email=request.email,
            password=request.password,
            name=request.name,
            role=request.role,
        )
    except WeakPassword as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    audit.record(session, action="user.registered", user_id=user.id, entity="user", entity_id=user.id)
    return TokenResponse(
        access_token=create_token(user.id, user.role), expires_in_hours=TOKEN_TTL_HOURS
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = users.authenticate(session, email=request.email, password=request.password)
    if user is None:
        # One message for both cases, so the response does not reveal which
        # email addresses have accounts.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
        )
    return TokenResponse(
        access_token=create_token(user.id, user.role), expires_in_hours=TOKEN_TTL_HOURS
    )


@router.get("/me", response_model=UserResponse)
def me(principal: Principal = Depends(current_user)) -> UserResponse:
    return UserResponse(
        id=principal.id,
        email=principal.email,
        name=None,
        role=principal.role,
        registration_no=principal.registration_no,
        organization_id=principal.organization_id,
    )
