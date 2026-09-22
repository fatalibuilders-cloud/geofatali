"""Boreholes, soil layers and field tests — the record of what is in the ground."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import Borehole, CptTest, DcpTest, LabTest, SoilLayer, SptTest
from ..security import Principal
from . import Conflict, NotFound
from .projects import get as get_project


def create_borehole(
    session: Session, principal: Principal, project_id: uuid.UUID, *, code: str, **fields: Any
) -> Borehole:
    project = get_project(session, principal, project_id)
    borehole = Borehole(project_id=project.id, code=code.strip(), **fields)
    session.add(borehole)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict(
            f"This project already has a borehole called {code!r}. Borehole codes "
            "identify a location on site, so they have to be unique within a project."
        ) from exc
    return borehole


def get_borehole(
    session: Session, principal: Principal, project_id: uuid.UUID, borehole_id: uuid.UUID
) -> Borehole:
    project = get_project(session, principal, project_id)
    borehole = session.execute(
        select(Borehole).where(Borehole.id == borehole_id, Borehole.project_id == project.id)
    ).scalar_one_or_none()
    if borehole is None:
        raise NotFound(f"No borehole {borehole_id} in project {project_id}")
    return borehole


def list_boreholes(session: Session, principal: Principal, project_id: uuid.UUID) -> list[Borehole]:
    project = get_project(session, principal, project_id)
    return list(
        session.execute(
            select(Borehole).where(Borehole.project_id == project.id).order_by(Borehole.code)
        ).scalars()
    )


def add_layer(
    session: Session,
    principal: Principal,
    project_id: uuid.UUID,
    borehole_id: uuid.UUID,
    *,
    top_depth_m: Decimal | float,
    bottom_depth_m: Decimal | float,
    classification_source: str,
    **fields: Any,
) -> SoilLayer:
    """Log one stratum.

    Depth ordering and overlap are enforced by the database (a CHECK and an
    EXCLUDE constraint). Both are translated here into something a site
    technician can act on, because "23P01: conflicting key value violates
    exclusion constraint" is not a message anyone can use.
    """
    borehole = get_borehole(session, principal, project_id, borehole_id)
    layer = SoilLayer(
        borehole_id=borehole.id,
        top_depth_m=Decimal(str(top_depth_m)),
        bottom_depth_m=Decimal(str(bottom_depth_m)),
        classification_source=classification_source,
        **fields,
    )
    session.add(layer)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        message = str(exc.orig)
        if "soil_layers_no_overlap" in message:
            raise Conflict(
                f"A layer from {top_depth_m} m to {bottom_depth_m} m overlaps one already "
                f"logged in this borehole. A borehole log has one stratum at each depth — "
                "check the depths, or edit the existing layer instead of adding another."
            ) from exc
        if "bottom_depth_m > top_depth_m" in message or "check constraint" in message.lower():
            raise Conflict(
                f"Bottom depth ({bottom_depth_m} m) must be below top depth ({top_depth_m} m). "
                "Depths are measured downward from ground level."
            ) from exc
        raise
    return layer


def layers(
    session: Session, principal: Principal, project_id: uuid.UUID, borehole_id: uuid.UUID
) -> list[SoilLayer]:
    borehole = get_borehole(session, principal, project_id, borehole_id)
    return list(
        session.execute(
            select(SoilLayer)
            .where(SoilLayer.borehole_id == borehole.id)
            .order_by(SoilLayer.top_depth_m)
        ).scalars()
    )


def reclassify_layer(
    session: Session,
    principal: Principal,
    project_id: uuid.UUID,
    borehole_id: uuid.UUID,
    layer_id: uuid.UUID,
    *,
    uscs_class: str | None = None,
    aashto_class: str | None = None,
    classification_source: str,
    confidence: float | None = None,
) -> tuple[SoilLayer, dict[str, Any]]:
    """Change a layer's classification, recording what it was.

    This is the edit an engineer makes when they disagree with a visual or AI
    classification, and it is one of the tracked audit actions. The new source
    must be supplied: correcting an AI class by hand makes it ENGINEER, and
    pretending otherwise would hide that a human overrode the model.
    """
    borehole = get_borehole(session, principal, project_id, borehole_id)
    layer = session.execute(
        select(SoilLayer).where(SoilLayer.id == layer_id, SoilLayer.borehole_id == borehole.id)
    ).scalar_one_or_none()
    if layer is None:
        raise NotFound(f"No soil layer {layer_id} in borehole {borehole_id}")

    before = {
        "uscs_class": layer.uscs_class,
        "aashto_class": layer.aashto_class,
        "classification_source": layer.classification_source,
        "confidence": None if layer.confidence is None else float(layer.confidence),
    }
    if uscs_class is not None:
        layer.uscs_class = uscs_class
    if aashto_class is not None:
        layer.aashto_class = aashto_class
    layer.classification_source = classification_source
    layer.confidence = None if confidence is None else Decimal(str(confidence))
    session.flush()
    return layer, before


def add_spt(
    session: Session,
    principal: Principal,
    project_id: uuid.UUID,
    borehole_id: uuid.UUID,
    **fields: Any,
) -> SptTest:
    borehole = get_borehole(session, principal, project_id, borehole_id)
    test = SptTest(borehole_id=borehole.id, **fields)
    session.add(test)
    session.flush()
    return test


def spt_for_borehole(
    session: Session, principal: Principal, project_id: uuid.UUID, borehole_id: uuid.UUID
) -> list[SptTest]:
    borehole = get_borehole(session, principal, project_id, borehole_id)
    return list(
        session.execute(
            select(SptTest).where(SptTest.borehole_id == borehole.id).order_by(SptTest.depth_m)
        ).scalars()
    )


def add_dcp(session: Session, principal: Principal, project_id: uuid.UUID, **fields: Any) -> DcpTest:
    project = get_project(session, principal, project_id)
    test = DcpTest(project_id=project.id, **fields)
    session.add(test)
    session.flush()
    return test


def add_cpt(session: Session, principal: Principal, project_id: uuid.UUID, **fields: Any) -> CptTest:
    project = get_project(session, principal, project_id)
    test = CptTest(project_id=project.id, **fields)
    session.add(test)
    session.flush()
    return test


def add_lab_test(
    session: Session,
    principal: Principal,
    project_id: uuid.UUID,
    borehole_id: uuid.UUID,
    layer_id: uuid.UUID,
    **fields: Any,
) -> LabTest:
    borehole = get_borehole(session, principal, project_id, borehole_id)
    layer = session.execute(
        select(SoilLayer).where(SoilLayer.id == layer_id, SoilLayer.borehole_id == borehole.id)
    ).scalar_one_or_none()
    if layer is None:
        raise NotFound(f"No soil layer {layer_id} in borehole {borehole_id}")
    test = LabTest(soil_layer_id=layer.id, **fields)
    session.add(test)
    session.flush()
    return test
