"""The audit log (spec section 50).

Append-only, enforced by a database trigger. It records the actions that
change what the project claims to be true: a soil classification edited, a
calculation re-run, the design standard changed, a report generated, an
engineer approving. Those are the moments someone will later need to
reconstruct.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import AuditLog

#: Actions worth keeping. Anything not on this list is ordinary traffic and
#: logging it would bury the entries that matter.
TRACKED_ACTIONS = frozenset({
    "project.created",
    "project.updated",
    "project.deleted",
    "project.standard_changed",
    "project.sector_changed",
    "borehole.created",
    "borehole.updated",
    "soil_layer.created",
    "soil_layer.classification_changed",
    "soil_layer.deleted",
    "calculation.run",
    "foundation.selected",
    "report.generated",
    "review.submitted",
    "review.approved",
    "review.rejected",
    "user.registered",
})


def record(
    session: Session,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    entity: str | None = None,
    entity_id: uuid.UUID | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    device_info: dict[str, Any] | None = None,
) -> AuditLog:
    if action not in TRACKED_ACTIONS:
        raise ValueError(
            f"{action!r} is not a tracked action. Add it to TRACKED_ACTIONS if it "
            "genuinely changes what the project asserts; otherwise do not log it."
        )
    entry = AuditLog(
        action=action,
        user_id=user_id,
        project_id=project_id,
        entity=entity,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        device_info=device_info,
    )
    session.add(entry)
    session.flush()
    return entry


def for_project(session: Session, project_id: uuid.UUID, *, limit: int = 100) -> list[AuditLog]:
    return list(
        session.execute(
            select(AuditLog)
            .where(AuditLog.project_id == project_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        ).scalars()
    )
