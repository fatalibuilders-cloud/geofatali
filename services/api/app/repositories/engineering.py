"""Calculations, foundations, reports and reviews — the evidence trail.

Everything in this module is append-only or revisioned. There is deliberately
no ``update_calculation`` and no ``update_report``, and the database refuses
the statements even if someone writes them by hand. A calculation is a record
of what the engine said, with which inputs, under which standard, at which
version; a report is what was issued to a client on a date. Editing either
destroys the only property that made it worth keeping.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import Calculation, Foundation, Report, Review
from ..security import Principal
from . import Conflict, NotFound
from .projects import get as get_project


def store_calculation(
    session: Session,
    principal: Principal,
    project_id: uuid.UUID,
    record: dict[str, Any],
) -> Calculation:
    """Persist an engine CalculationRecord exactly as it was produced.

    ``record`` is the dict from ``CalculationRecord.as_dict()``. It is stored
    whole — inputs, warnings, provenance and all — so the calculation can be
    replayed years later against the engine version named in it.

    A refusal (``INSUFFICIENT_DATA``) is stored too. "We could not calculate
    this on 12 March, and here is what was missing" is part of the project
    history, and dropping it would make the record look like the question was
    never asked.
    """
    project = get_project(session, principal, project_id)
    calculation = Calculation(
        project_id=project.id,
        calculation_type=record["calculation_type"],
        method=record["method"],
        standard=record.get("standard"),
        standard_edition=record.get("standard_edition"),
        engine_version=record["engine_version"],
        status=record["status"],
        inputs=record.get("inputs") or {},
        results=record.get("results") or {},
        warnings=record.get("warnings") or [],
        provenance=record.get("provenance") or {},
        preliminary=bool(record.get("preliminary", True)),
        created_by=principal.id,
    )
    session.add(calculation)
    session.flush()
    return calculation


def get_calculation(
    session: Session, principal: Principal, project_id: uuid.UUID, calculation_id: uuid.UUID
) -> Calculation:
    project = get_project(session, principal, project_id)
    calculation = session.execute(
        select(Calculation).where(
            Calculation.id == calculation_id, Calculation.project_id == project.id
        )
    ).scalar_one_or_none()
    if calculation is None:
        raise NotFound(f"No calculation {calculation_id} in project {project_id}")
    return calculation


def calculations_for(
    session: Session,
    principal: Principal,
    project_id: uuid.UUID,
    *,
    calculation_type: str | None = None,
    limit: int = 100,
) -> list[Calculation]:
    """Every calculation, newest first — including superseded ones.

    Re-running a calculation does not replace the previous run, so this is the
    full history. Callers wanting only the latest of each type use
    ``latest_by_type``.
    """
    project = get_project(session, principal, project_id)
    query = select(Calculation).where(Calculation.project_id == project.id)
    if calculation_type:
        query = query.where(Calculation.calculation_type == calculation_type)
    return list(
        session.execute(
            query.order_by(Calculation.created_at.desc(), Calculation.id.desc()).limit(limit)
        ).scalars()
    )


def latest_by_type(
    session: Session, principal: Principal, project_id: uuid.UUID
) -> dict[str, Calculation]:
    """The most recent run of each calculation type — what the report shows."""
    latest: dict[str, Calculation] = {}
    for calculation in calculations_for(session, principal, project_id, limit=500):
        latest.setdefault(calculation.calculation_type, calculation)
    return latest


def record_candidates(
    session: Session,
    principal: Principal,
    project_id: uuid.UUID,
    screening: Calculation,
    candidates: list[dict[str, Any]],
) -> list[Foundation]:
    """Store the screened options, each with the construction sequence for it.

    Every one is stored with status 'candidate'. Nothing in this codebase sets
    a foundation to 'selected' — that is ``select_foundation``, which a person
    calls.
    """
    stored: list[Foundation] = []
    for candidate in candidates:
        foundation = Foundation(
            project_id=project_id,
            foundation_type=candidate["foundation_type"],
            geometry={},
            status="candidate",
            calculation_id=screening.id,
            construction_steps=candidate.get("construction_steps", []),
            notes=candidate.get("status"),
        )
        session.add(foundation)
        stored.append(foundation)
    session.flush()
    return stored


def select_foundation(
    session: Session, principal: Principal, project_id: uuid.UUID, foundation_id: uuid.UUID
) -> Foundation:
    """Mark one candidate as the chosen system. A person's decision, recorded."""
    project = get_project(session, principal, project_id)
    foundation = session.execute(
        select(Foundation).where(
            Foundation.id == foundation_id, Foundation.project_id == project.id
        )
    ).scalar_one_or_none()
    if foundation is None:
        raise NotFound(f"No foundation {foundation_id} in project {project_id}")
    for other in session.execute(
        select(Foundation).where(
            Foundation.project_id == project.id, Foundation.status == "selected"
        )
    ).scalars():
        other.status = "candidate"
    foundation.status = "selected"
    session.flush()
    return foundation


def next_revision(session: Session, project_id: uuid.UUID, report_type: str) -> int:
    highest = session.execute(
        select(func.max(Report.revision)).where(
            Report.project_id == project_id, Report.report_type == report_type
        )
    ).scalar_one_or_none()
    return (highest or 0) + 1


def store_report(
    session: Session,
    principal: Principal,
    project_id: uuid.UUID,
    *,
    document: dict[str, Any],
    engine_version: str,
    banner: str,
    report_type: str = "geotechnical_assessment",
    ai_model: str | None = None,
    storage_key: str | None = None,
) -> Report:
    """Issue a new revision. Never overwrites an earlier one."""
    project = get_project(session, principal, project_id)
    report = Report(
        project_id=project.id,
        report_type=report_type,
        revision=next_revision(session, project.id, report_type),
        storage_key=storage_key,
        document=document,
        generated_by=principal.id,
        engine_version=engine_version,
        ai_model=ai_model,
        banner=banner,
    )
    session.add(report)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict(
            "Another revision of this report was issued at the same moment. Retry — "
            "the new one will take the next revision number."
        ) from exc
    return report


def reports_for(session: Session, principal: Principal, project_id: uuid.UUID) -> list[Report]:
    project = get_project(session, principal, project_id)
    return list(
        session.execute(
            select(Report)
            .where(Report.project_id == project.id)
            .order_by(Report.report_type, Report.revision.desc())
        ).scalars()
    )


def submit_review(
    session: Session,
    principal: Principal,
    project_id: uuid.UUID,
    *,
    status: str,
    comments: str | None = None,
    report_id: uuid.UUID | None = None,
) -> Review:
    """An engineer's verdict on the project.

    Approval is the state change that takes the PRELIMINARY banner off a
    report, so it is gated three ways: the reviewer must hold the engineer
    role, they must have a board registration number on file, and an approval
    is always stamped with the moment it was signed. The database rejects an
    APPROVED row with no ``signed_at`` regardless of what this function does.
    """
    if status not in ("PENDING", "COMMENTS", "APPROVED", "REJECTED"):
        raise ValueError(f"Unknown review status {status!r}")
    project = get_project(session, principal, project_id)

    if status == "APPROVED":
        if not principal.at_least("engineer"):
            raise Conflict(
                "Only a registered engineer may approve a geotechnical assessment. "
                "This account does not hold the engineer role."
            )
        if not principal.registration_no:
            raise Conflict(
                "Approval requires a board registration number on the reviewing "
                "account. A signature nobody can check is not a signature."
            )

    review = Review(
        project_id=project.id,
        report_id=report_id,
        reviewer_id=principal.id,
        status=status,
        comments=comments,
        signed_at=datetime.now(timezone.utc) if status == "APPROVED" else None,
    )
    session.add(review)
    session.flush()
    return review


def reviews_for(session: Session, principal: Principal, project_id: uuid.UUID) -> list[Review]:
    project = get_project(session, principal, project_id)
    return list(
        session.execute(
            select(Review)
            .where(Review.project_id == project.id)
            .order_by(Review.created_at.desc())
        ).scalars()
    )


def is_approved(session: Session, principal: Principal, project_id: uuid.UUID) -> bool:
    """Has a registered engineer signed this project off?"""
    return any(r.status == "APPROVED" for r in reviews_for(session, principal, project_id))
