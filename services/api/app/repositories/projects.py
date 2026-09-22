"""Projects, and the access rule every other repository depends on."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db.models import Project
from ..security import Principal
from . import NotFound

#: Fields a user may change after creation. `created_by` and `id` are not on
#: this list, and neither is anything that would rewrite history.
MUTABLE_FIELDS = frozenset({
    "name", "client_name", "sector", "project_type", "country",
    "administrative_area", "latitude", "longitude", "floors", "basement",
    "basement_depth_m", "length_m", "width_m", "structural_system",
    "design_standard", "status",
})


def _visible_to(principal: Principal):
    """The rows this principal may see.

    Their own projects, plus anything belonging to their organisation. An
    admin sees everything, because someone has to be able to answer a support
    request; every such read lands in the audit log.
    """
    if principal.at_least("admin"):
        return Project.id == Project.id  # always true
    clauses = [Project.created_by == principal.id]
    if principal.organization_id is not None:
        clauses.append(Project.organization_id == principal.organization_id)
    return or_(*clauses)


def create(
    session: Session,
    principal: Principal,
    *,
    name: str,
    sector: str = "buildings_low_rise",
    design_standard: str = "eurocode",
    **fields: Any,
) -> Project:
    unknown = set(fields) - MUTABLE_FIELDS
    if unknown:
        raise ValueError(f"Unknown project fields: {sorted(unknown)}")
    project = Project(
        name=name,
        sector=sector,
        design_standard=design_standard,
        created_by=principal.id,
        organization_id=principal.organization_id,
        **fields,
    )
    session.add(project)
    session.flush()
    return project


def get(session: Session, principal: Principal, project_id: uuid.UUID) -> Project:
    """The project, if this principal may see it. Otherwise NotFound.

    Every nested resource resolves through this function, so there is exactly
    one place where project visibility is decided.
    """
    project = session.execute(
        select(Project).where(Project.id == project_id, _visible_to(principal))
    ).scalar_one_or_none()
    if project is None:
        raise NotFound(f"No project {project_id}")
    return project


def list_for(session: Session, principal: Principal, *, limit: int = 50, offset: int = 0) -> list[Project]:
    return list(
        session.execute(
            select(Project)
            .where(_visible_to(principal))
            .order_by(Project.updated_at.desc())
            .limit(min(limit, 200))
            .offset(offset)
        ).scalars()
    )


def update(
    session: Session, principal: Principal, project_id: uuid.UUID, **fields: Any
) -> tuple[Project, dict[str, Any]]:
    """Apply changes, and return what actually changed for the audit log."""
    unknown = set(fields) - MUTABLE_FIELDS
    if unknown:
        raise ValueError(f"Fields that cannot be changed: {sorted(unknown)}")
    project = get(session, principal, project_id)
    changed: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        before = getattr(project, key)
        if before != value:
            changed[key] = {"from": str(before), "to": str(value)}
            setattr(project, key, value)
    session.flush()
    return project, changed


def delete(session: Session, principal: Principal, project_id: uuid.UUID) -> None:
    """Remove a project and everything under it.

    This is a real delete, not a flag. Spec section 49 requires data deletion
    to be possible, and a soft delete that leaves the site data in place is not
    deletion. The cascade takes the boreholes, layers, media, calculations and
    reports with it.
    """
    project = get(session, principal, project_id)
    session.delete(project)
    session.flush()
