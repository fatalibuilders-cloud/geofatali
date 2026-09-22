"""Calculations, foundations, reports and reviews, stored against a project.

The stateless endpoints in ``main.py`` are the quick calculators: ask a
question, get an answer, nothing kept. These are the project endpoints: the
same engine, but every run is written to the calculation history with its
inputs, its method, its standard and its engine version, and nothing that is
written can later be edited.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from geofatali_engine.bearing.capacity import Footing, bearing_capacity
from geofatali_engine.foundations.screening import ScreeningInput, screen_foundations
from geofatali_engine.foundations.sizing import size_footing
from geofatali_engine.report.markdown import render_markdown
from geofatali_engine.record import CalculationRecord
from geofatali_engine.report.model import Review as ReportReview
from geofatali_engine.report.model import build_report
from geofatali_engine.version import ENGINE_VERSION

from ..api_models import (
    CalculationResponse,
    ReportResponse,
    ReviewRequest,
    ReviewResponse,
)
from ..db.base import get_session
from ..repositories import Conflict, NotFound, audit
from ..repositories import engineering as repo
from ..repositories import users
from ..repositories import projects as project_repo
from ..schemas import BearingCapacityRequest, FoundationScreeningRequest, FootingSizingRequest
from ..security import Principal, current_user
from .errors import http_error

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["project calculations"])


def _calculation_response(calculation) -> CalculationResponse:
    return CalculationResponse(
        id=calculation.id,
        calculation_type=calculation.calculation_type,
        method=calculation.method,
        standard=calculation.standard,
        engine_version=calculation.engine_version,
        status=calculation.status,
        preliminary=calculation.preliminary,
        created_at=calculation.created_at,
        results=calculation.results,
        warnings=calculation.warnings,
    )


def _store(session, principal, project_id, record) -> dict:
    """Persist an engine record and return it with its stored id."""
    try:
        stored = repo.store_calculation(session, principal, project_id, record.as_dict())
    except NotFound as exc:
        raise http_error(exc) from exc
    audit.record(
        session, action="calculation.run", user_id=principal.id, project_id=project_id,
        entity="calculation", entity_id=stored.id,
        new_value={
            "type": record.calculation_type,
            "method": record.method,
            "status": record.status.value,
        },
    )
    payload = record.as_dict()
    payload["id"] = str(stored.id)
    return payload


@router.post("/calculations/bearing-capacity", status_code=status.HTTP_201_CREATED)
def run_bearing_capacity(
    project_id: uuid.UUID,
    request: BearingCapacityRequest,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    from ..main import _ground, _soil  # shared request translation

    record = bearing_capacity(
        soil=_soil(request.soil),
        footing=Footing(
            width_m=request.foundation.width_m,
            depth_m=request.foundation.depth_m,
            length_m=request.foundation.length_m,
            shape=request.foundation.shape,
        ),
        ground=_ground(request.groundwater),
        method=request.method,
        factor_of_safety=request.safety_factor,
        standard_id=request.standard,
    )
    return _store(session, principal, project_id, record)


@router.post("/calculations/footing", status_code=status.HTTP_201_CREATED)
def run_footing(
    project_id: uuid.UUID,
    request: FootingSizingRequest,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    from ..main import _ground, _soil

    record = size_footing(
        service_load_kn=request.service_load_kn,
        soil=_soil(request.soil),
        depth_m=request.depth_m,
        shape=request.shape,
        length_over_width=request.length_over_width,
        ground=_ground(request.groundwater),
        method=request.method,
        factor_of_safety=request.safety_factor,
        standard_id=request.standard,
        max_width_m=request.max_width_m,
    )
    return _store(session, principal, project_id, record)


@router.post("/calculations/foundation-options", status_code=status.HTTP_201_CREATED)
def run_screening(
    project_id: uuid.UUID,
    request: FoundationScreeningRequest,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Screen the options and store every candidate with its construction steps."""
    from ..main import _findings

    record = screen_foundations(ScreeningInput(
        sector_id=request.sector,
        service_load_kn=request.service_load_kn,
        net_allowable_kpa=request.net_allowable_kpa,
        required_footing_width_m=request.required_footing_width_m,
        utilisation=request.utilisation,
        total_settlement_mm=request.total_settlement_mm,
        column_spacing_m=request.column_spacing_m,
        footprint_area_m2=request.footprint_area_m2,
        number_of_columns=request.number_of_columns,
        floors=request.floors,
        competent_stratum_depth_m=request.competent_stratum_depth_m,
        trial_founding_depth_m=request.trial_founding_depth_m,
        uplift_kn=request.uplift_kn,
        findings=_findings(request.findings),
        standard_id=request.standard,
    ))
    payload = _store(session, principal, project_id, record)
    stored = repo.get_calculation(session, principal, project_id, uuid.UUID(payload["id"]))
    foundations = repo.record_candidates(
        session, principal, project_id, stored, record.results.get("candidates", [])
    )
    payload["foundation_ids"] = [str(f.id) for f in foundations]
    return payload


@router.get("/calculations", response_model=list[CalculationResponse])
def list_calculations(
    project_id: uuid.UUID,
    calculation_type: str | None = None,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[CalculationResponse]:
    """The full history, newest first. Re-runs do not replace earlier runs."""
    try:
        records = repo.calculations_for(
            session, principal, project_id, calculation_type=calculation_type
        )
    except NotFound as exc:
        raise http_error(exc) from exc
    return [_calculation_response(c) for c in records]


@router.get("/calculations/{calculation_id}")
def get_calculation(
    project_id: uuid.UUID,
    calculation_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """One calculation in full — everything needed to reproduce it."""
    try:
        calculation = repo.get_calculation(session, principal, project_id, calculation_id)
    except NotFound as exc:
        raise http_error(exc) from exc
    return {
        "id": str(calculation.id),
        "calculation_type": calculation.calculation_type,
        "method": calculation.method,
        "standard": calculation.standard,
        "standard_edition": calculation.standard_edition,
        "engine_version": calculation.engine_version,
        "status": calculation.status,
        "preliminary": calculation.preliminary,
        "inputs": calculation.inputs,
        "results": calculation.results,
        "warnings": calculation.warnings,
        "provenance": calculation.provenance,
        "created_at": calculation.created_at.isoformat(),
    }


@router.post("/foundations/{foundation_id}/select")
def select_foundation(
    project_id: uuid.UUID,
    foundation_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Record which candidate was chosen. A person's decision, never the engine's."""
    try:
        foundation = repo.select_foundation(session, principal, project_id, foundation_id)
    except NotFound as exc:
        raise http_error(exc) from exc
    audit.record(
        session, action="foundation.selected", user_id=principal.id, project_id=project_id,
        entity="foundation", entity_id=foundation.id,
        new_value={"foundation_type": foundation.foundation_type},
    )
    return {
        "id": str(foundation.id),
        "foundation_type": foundation.foundation_type,
        "status": foundation.status,
        "construction_steps": foundation.construction_steps,
    }


@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def generate_report(
    project_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> ReportResponse:
    """Assemble a report from everything stored, and issue it as a new revision.

    The banner is decided here and nowhere else: PRELIMINARY unless a
    registered engineer has approved this project through the review workflow.
    """
    try:
        project = project_repo.get(session, principal, project_id)
    except NotFound as exc:
        raise http_error(exc) from exc

    latest = repo.latest_by_type(session, principal, project_id)

    def stored(name: str) -> CalculationRecord | None:
        """Rehydrate a stored calculation into the record the engine produced.

        Not an adapter or a shim: ``CalculationRecord.from_dict`` is the exact
        inverse of what was written, so the report is built from the same
        object it would have had if the calculation had just been run.
        """
        row = latest.get(name)
        if row is None:
            return None
        return CalculationRecord.from_dict({
            "calculation_type": row.calculation_type,
            "method": row.method,
            "status": row.status,
            "standard": row.standard,
            "standard_edition": row.standard_edition,
            "engine_version": row.engine_version,
            "inputs": row.inputs,
            "results": row.results,
            "warnings": row.warnings,
            "provenance": row.provenance,
            "created_at": row.created_at.isoformat(),
        })

    gaps = [
        w.get("message", "")
        for row in latest.values()
        for w in (row.warnings or [])
        if w.get("severity") in ("CRITICAL", "WARNING")
    ]

    document = build_report(
        project_name=project.name,
        client_name=project.client_name,
        site_location=project.administrative_area or project.country,
        sector_id=project.sector,
        standard_id=project.design_standard,
        revision=repo.next_revision(session, project.id, "geotechnical_assessment"),
        bearing=stored("bearing_capacity"),
        sizing=stored("footing_sizing"),
        screening=stored("foundation_screening"),
        loads=stored("column_load_estimate"),
        settlement=[s for s in (stored("consolidation_settlement"), stored("elastic_settlement")) if s],
        data_gaps=list(dict.fromkeys(gaps)),
    )
    # The banner comes off only for an approval by a registered engineer, and
    # the report then names who signed it.
    approval = next(
        (r for r in repo.reviews_for(session, principal, project_id) if r.status == "APPROVED"),
        None,
    )
    if approval is not None:
        reviewer = users.by_id(session, approval.reviewer_id)
        document.review = ReportReview(
            reviewer_name=reviewer.name or reviewer.email,
            registration_number=reviewer.registration_no or "",
            status=approval.status,
            comments=approval.comments or "",
            signed_at=approval.signed_at.isoformat() if approval.signed_at else "",
        )
        document.section("Engineer review").absent_reason = None
        document.section("Engineer review").table = [
            {"field": "Reviewer", "value": document.review.reviewer_name},
            {"field": "Registration", "value": document.review.registration_number},
            {"field": "Status", "value": document.review.status},
            {"field": "Signed", "value": document.review.signed_at},
            {"field": "Comments", "value": document.review.comments},
        ]

    payload = document.as_dict()
    payload["markdown"] = render_markdown(document)

    report = repo.store_report(
        session, principal, project_id,
        document=payload,
        engine_version=ENGINE_VERSION,
        banner=document.banner,
    )
    audit.record(
        session, action="report.generated", user_id=principal.id, project_id=project_id,
        entity="report", entity_id=report.id,
        new_value={"revision": report.revision, "banner": report.banner},
    )
    return ReportResponse(
        id=report.id,
        report_type=report.report_type,
        revision=report.revision,
        banner=report.banner,
        engine_version=report.engine_version,
        created_at=report.created_at,
    )


@router.get("/reports", response_model=list[ReportResponse])
def list_reports(
    project_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[ReportResponse]:
    try:
        reports = repo.reports_for(session, principal, project_id)
    except NotFound as exc:
        raise http_error(exc) from exc
    return [
        ReportResponse(
            id=r.id, report_type=r.report_type, revision=r.revision,
            banner=r.banner, engine_version=r.engine_version, created_at=r.created_at,
        )
        for r in reports
    ]


@router.post("/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def submit_review(
    project_id: uuid.UUID,
    request: ReviewRequest,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> ReviewResponse:
    """An engineer's verdict. Approval is what clears the preliminary banner."""
    try:
        review = repo.submit_review(
            session, principal, project_id,
            status=request.status, comments=request.comments, report_id=request.report_id,
        )
    except NotFound as exc:
        raise http_error(exc) from exc
    except Conflict as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    audit.record(
        session,
        action={"APPROVED": "review.approved", "REJECTED": "review.rejected"}.get(
            request.status, "review.submitted"
        ),
        user_id=principal.id, project_id=project_id,
        entity="review", entity_id=review.id,
        new_value={"status": review.status},
    )
    return ReviewResponse(
        id=review.id, status=review.status, comments=review.comments,
        reviewer_id=review.reviewer_id, signed_at=review.signed_at, created_at=review.created_at,
    )


@router.get("/reviews", response_model=list[ReviewResponse])
def list_reviews(
    project_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[ReviewResponse]:
    try:
        reviews = repo.reviews_for(session, principal, project_id)
    except NotFound as exc:
        raise http_error(exc) from exc
    return [
        ReviewResponse(
            id=r.id, status=r.status, comments=r.comments,
            reviewer_id=r.reviewer_id, signed_at=r.signed_at, created_at=r.created_at,
        )
        for r in reviews
    ]
