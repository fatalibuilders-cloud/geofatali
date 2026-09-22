"""Repository errors, translated to HTTP once rather than at every call site."""

from __future__ import annotations

from fastapi import HTTPException, status

from ..repositories import Conflict, Immutable, NotFound


def http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFound):
        # Deliberately the same response whether the row is absent or simply
        # not this user's: a 403 would confirm the id exists.
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, Immutable):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, Conflict):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise exc
