"""Projects: the container everything else hangs from."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from geofatali_engine.sectors import SECTORS
from geofatali_engine.standards import STANDARDS

from ..api_models import ProjectCreate, ProjectResponse, ProjectUpdate
from ..db.base import get_session
from ..repositories import NotFound, audit
from ..repositories import projects as repo
from ..security import Principal, current_user
from .errors import http_error

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _validate_taxonomy(sector: str | None, standard: str | None) -> None:
    """Reject a sector or standard the engine does not know.

    Storing an unknown sector would silently change which checks govern the
    project — and the screen would come back with no candidates and no
    explanation. Better to refuse the write and name the valid values.
    """
    if sector is not None and sector not in SECTORS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "UNKNOWN_SECTOR",
                "message": f"{sector!r} is not a sector the engine models.",
                "known": sorted(SECTORS),
            },
        )
    if standard is not None and standard not in STANDARDS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "UNKNOWN_STANDARD",
                "message": f"{standard!r} is not a configured design standard.",
                "known": sorted(STANDARDS),
            },
        )


def _response(project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        client_name=project.client_name,
        sector=project.sector,
        design_standard=project.design_standard,
        country=project.country,
        administrative_area=project.administrative_area,
        latitude=project.latitude,
        longitude=project.longitude,
        floors=project.floors,
        basement=project.basement,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreate,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> ProjectResponse:
    _validate_taxonomy(request.sector, request.design_standard)
    project = repo.create(session, principal, **request.model_dump())
    audit.record(
        session,
        action="project.created",
        user_id=principal.id,
        project_id=project.id,
        entity="project",
        entity_id=project.id,
        new_value={"name": project.name, "sector": project.sector},
    )
    return _response(project)


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[ProjectResponse]:
    return [_response(p) for p in repo.list_for(session, principal, limit=limit, offset=offset)]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> ProjectResponse:
    try:
        return _response(repo.get(session, principal, project_id))
    except NotFound as exc:
        raise http_error(exc) from exc


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: uuid.UUID,
    request: ProjectUpdate,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> ProjectResponse:
    _validate_taxonomy(request.sector, request.design_standard)
    fields = {k: v for k, v in request.model_dump().items() if v is not None}
    try:
        project, changed = repo.update(session, principal, project_id, **fields)
    except NotFound as exc:
        raise http_error(exc) from exc

    if changed:
        audit.record(
            session,
            action="project.updated",
            user_id=principal.id,
            project_id=project.id,
            entity="project",
            entity_id=project.id,
            new_value=changed,
        )
    # Changing either of these changes what every subsequent calculation means,
    # so they are logged as their own events rather than buried in a diff.
    if "sector" in changed:
        audit.record(
            session, action="project.sector_changed", user_id=principal.id,
            project_id=project.id, entity="project", entity_id=project.id,
            old_value={"sector": changed["sector"]["from"]},
            new_value={"sector": changed["sector"]["to"]},
        )
    if "design_standard" in changed:
        audit.record(
            session, action="project.standard_changed", user_id=principal.id,
            project_id=project.id, entity="project", entity_id=project.id,
            old_value={"standard": changed["design_standard"]["from"]},
            new_value={"standard": changed["design_standard"]["to"]},
        )
    return _response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> None:
    """Delete a project and everything under it.

    A real delete. The audit entry is written first, because the cascade will
    take the project's own audit rows with it — what survives is the record in
    the actor's own history that the deletion happened.
    """
    try:
        repo.get(session, principal, project_id)
    except NotFound as exc:
        raise http_error(exc) from exc
    audit.record(
        session, action="project.deleted", user_id=principal.id,
        entity="project", entity_id=project_id,
    )
    repo.delete(session, principal, project_id)


@router.get("/{project_id}/audit")
def project_audit(
    project_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    """What has been changed on this project, newest first."""
    try:
        repo.get(session, principal, project_id)
    except NotFound as exc:
        raise http_error(exc) from exc
    return [
        {
            "action": entry.action,
            "entity": entry.entity,
            "entity_id": str(entry.entity_id) if entry.entity_id else None,
            "old_value": entry.old_value,
            "new_value": entry.new_value,
            "created_at": entry.created_at.isoformat(),
        }
        for entry in audit.for_project(session, project_id)
    ]
