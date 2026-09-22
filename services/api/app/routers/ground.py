"""Boreholes, soil layers and field tests."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from geofatali_engine.soil import correlations as corr

from ..api_models import (
    BoreholeCreate,
    BoreholeResponse,
    ReclassifyRequest,
    SoilLayerCreate,
    SoilLayerResponse,
    SptCreate,
)
from ..db.base import get_session
from ..repositories import Conflict, NotFound, audit
from ..repositories import ground as repo
from ..security import Principal, current_user
from .errors import http_error

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["ground"])


def _f(value) -> float | None:
    return None if value is None else float(value)


def _borehole(b) -> BoreholeResponse:
    return BoreholeResponse(
        id=b.id, code=b.code,
        ground_elevation_m=_f(b.ground_elevation_m),
        total_depth_m=_f(b.total_depth_m),
        groundwater_depth_m=_f(b.groundwater_depth_m),
        groundwater_observed=b.groundwater_observed,
        drilling_method=b.drilling_method,
        date_drilled=b.date_drilled,
        notes=b.notes,
    )


def _layer(layer) -> SoilLayerResponse:
    return SoilLayerResponse(
        id=layer.id,
        top_depth_m=float(layer.top_depth_m),
        bottom_depth_m=float(layer.bottom_depth_m),
        description=layer.description,
        uscs_class=layer.uscs_class,
        aashto_class=layer.aashto_class,
        confidence=_f(layer.confidence),
        classification_source=layer.classification_source,
    )


@router.post("/boreholes", response_model=BoreholeResponse, status_code=status.HTTP_201_CREATED)
def create_borehole(
    project_id: uuid.UUID,
    request: BoreholeCreate,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> BoreholeResponse:
    fields = request.model_dump()
    code = fields.pop("code")
    try:
        borehole = repo.create_borehole(session, principal, project_id, code=code, **fields)
    except (NotFound, Conflict) as exc:
        raise http_error(exc) from exc
    audit.record(
        session, action="borehole.created", user_id=principal.id, project_id=project_id,
        entity="borehole", entity_id=borehole.id, new_value={"code": borehole.code},
    )
    return _borehole(borehole)


@router.get("/boreholes", response_model=list[BoreholeResponse])
def list_boreholes(
    project_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[BoreholeResponse]:
    try:
        return [_borehole(b) for b in repo.list_boreholes(session, principal, project_id)]
    except NotFound as exc:
        raise http_error(exc) from exc


@router.post(
    "/boreholes/{borehole_id}/layers",
    response_model=SoilLayerResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_layer(
    project_id: uuid.UUID,
    borehole_id: uuid.UUID,
    request: SoilLayerCreate,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> SoilLayerResponse:
    """Log one stratum. Overlapping an existing layer is refused, with a reason."""
    try:
        layer = repo.add_layer(session, principal, project_id, borehole_id, **request.model_dump())
    except (NotFound, Conflict) as exc:
        raise http_error(exc) from exc
    audit.record(
        session, action="soil_layer.created", user_id=principal.id, project_id=project_id,
        entity="soil_layer", entity_id=layer.id,
        new_value={
            "top_depth_m": float(layer.top_depth_m),
            "bottom_depth_m": float(layer.bottom_depth_m),
            "uscs_class": layer.uscs_class,
            "source": layer.classification_source,
        },
    )
    return _layer(layer)


@router.get("/boreholes/{borehole_id}/layers", response_model=list[SoilLayerResponse])
def list_layers(
    project_id: uuid.UUID,
    borehole_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[SoilLayerResponse]:
    try:
        return [_layer(layer) for layer in repo.layers(session, principal, project_id, borehole_id)]
    except NotFound as exc:
        raise http_error(exc) from exc


@router.patch(
    "/boreholes/{borehole_id}/layers/{layer_id}/classification",
    response_model=SoilLayerResponse,
)
def reclassify(
    project_id: uuid.UUID,
    borehole_id: uuid.UUID,
    layer_id: uuid.UUID,
    request: ReclassifyRequest,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> SoilLayerResponse:
    """Correct a layer's classification.

    This is how an engineer overrides a visual or AI class. The change is
    audited with the previous value, because "the model said SC and a person
    changed it to CH" is exactly the kind of thing a reviewer needs to see.
    """
    try:
        layer, before = repo.reclassify_layer(
            session, principal, project_id, borehole_id, layer_id, **request.model_dump()
        )
    except NotFound as exc:
        raise http_error(exc) from exc
    audit.record(
        session, action="soil_layer.classification_changed", user_id=principal.id,
        project_id=project_id, entity="soil_layer", entity_id=layer.id,
        old_value=before,
        new_value={
            "uscs_class": layer.uscs_class,
            "aashto_class": layer.aashto_class,
            "classification_source": layer.classification_source,
            "confidence": _f(layer.confidence),
        },
    )
    return _layer(layer)


@router.post("/boreholes/{borehole_id}/spt", status_code=status.HTTP_201_CREATED)
def add_spt(
    project_id: uuid.UUID,
    borehole_id: uuid.UUID,
    request: SptCreate,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Record an SPT, storing the raw count and the corrections separately.

    The correction is run by the engine and every factor is stored, so the
    corrected value can always be traced back to the blow count that was
    actually recorded on site. Storing only N60 would make the raw measurement
    unrecoverable and the correction unrepeatable.
    """
    correction = corr.correct_spt(
        n_raw=request.n_raw,
        energy_ratio_percent=request.energy_ratio_percent,
        borehole_diameter_mm=request.borehole_diameter_mm,
        rod_length_m=request.rod_length_m,
        effective_overburden_kpa=request.effective_overburden_kpa,
    )
    try:
        test = repo.add_spt(
            session, principal, project_id, borehole_id,
            depth_m=Decimal(str(request.depth_m)),
            seating_blows=request.seating_blows,
            blows_1=request.blows_1,
            blows_2=request.blows_2,
            blows_3=request.blows_3,
            n_raw=request.n_raw,
            n60=Decimal(str(round(correction.n60, 2))),
            n1_60=None if correction.n1_60 is None else Decimal(str(round(correction.n1_60, 2))),
            correction_method=correction.method,
            correction_factors=correction.as_dict(),
            equipment_data={
                "energy_ratio_percent": request.energy_ratio_percent,
                "borehole_diameter_mm": request.borehole_diameter_mm,
                "rod_length_m": request.rod_length_m,
            },
        )
    except NotFound as exc:
        raise http_error(exc) from exc
    return {
        "id": str(test.id),
        "depth_m": float(test.depth_m),
        "n_raw": test.n_raw,
        "n60": float(test.n60),
        "n1_60": None if test.n1_60 is None else float(test.n1_60),
        "correction": correction.as_dict(),
        "warnings": correction.warnings.as_list(),
    }


@router.get("/boreholes/{borehole_id}/spt")
def list_spt(
    project_id: uuid.UUID,
    borehole_id: uuid.UUID,
    principal: Principal = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    try:
        tests = repo.spt_for_borehole(session, principal, project_id, borehole_id)
    except NotFound as exc:
        raise http_error(exc) from exc
    return [
        {
            "id": str(t.id),
            "depth_m": float(t.depth_m),
            "n_raw": t.n_raw,
            "n60": _f(t.n60),
            "n1_60": _f(t.n1_60),
            "correction_method": t.correction_method,
        }
        for t in tests
    ]
