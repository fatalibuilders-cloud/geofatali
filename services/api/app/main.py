"""GeoFatali calculation API.

A thin HTTP surface over the engineering engine. It does three things and
nothing else:

  1. validate the request shape;
  2. call the engine;
  3. return the engine's CalculationRecord verbatim, including its warnings,
     its provenance and its engine version.

It never computes anything itself, it never fills in a missing value, and it
never rewrites a refusal into a number. An ``INSUFFICIENT_DATA`` status comes
back as a 200 with that status in the body, because "we cannot answer, and
here is exactly what is missing" is a successful, useful response — not an
error. Impossible input (a negative width, a 90-degree friction angle) is a
422, because that is the caller's bug.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from geofatali_engine.ai.provider import (
    SYSTEM_PROMPT,
    FabricatedMeasurement,
    observation_from_payload,
)
from geofatali_engine.bearing.capacity import (
    Footing,
    GroundConditions,
    SoilParameters,
    bearing_capacity,
)
from geofatali_engine.foundations.screening import ScreeningInput, screen_foundations
from geofatali_engine.foundations.sizing import eccentricity_check, size_footing
from geofatali_engine.foundations.steps import GroundFindings, construction_steps, steps_as_dicts
from geofatali_engine.foundations.types import FOUNDATION_TYPES
from geofatali_engine.loads.estimator import ColumnGeometry, estimate_column_load
from geofatali_engine.provenance import Source
from geofatali_engine.record import CalculationRecord
from geofatali_engine.sectors import CHECKS, SECTORS
from geofatali_engine.settlement.consolidation import consolidation_settlement
from geofatali_engine.settlement.elastic import elastic_settlement
from geofatali_engine.soil import correlations as corr
from geofatali_engine.soil.uscs import IndexTests, classify_uscs, swell_potential
from geofatali_engine.standards import METHOD_REFERENCES, STANDARDS
from geofatali_engine.version import ENGINE_VERSION
from geofatali_engine.warnings import InvalidInput

from .db.base import engine as db_engine
from .db.migrate import current_version
from .routers import auth, ground, project_calculations, projects
from .schemas import (
    BearingCapacityRequest,
    ClassificationRequest,
    ColumnLoadRequest,
    ConsolidationRequest,
    DcpRequest,
    ElasticSettlementRequest,
    FindingsIn,
    FoundationScreeningRequest,
    FootingSizingRequest,
    SoilAnalysisIn,
    SptCorrectionRequest,
    StepsRequest,
)

def _lan_addresses() -> list[str]:
    """Every address this machine is reachable on, for the startup banner.

    Printed because the commonest failure when testing from a phone is not
    knowing which address to type, or not realising the server bound only to
    localhost. Showing the answer beats explaining how to find it.
    """
    import socket

    found: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            address = info[4][0]
            if address not in found and not address.startswith("127."):
                found.append(address)
    except OSError:
        pass
    if not found:
        # getaddrinfo can miss the LAN address; ask the routing table instead.
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.connect(("192.168.1.1", 1))  # no packet is sent
            found.append(probe.getsockname()[0])
            probe.close()
        except OSError:
            pass
    return found


app = FastAPI(
    title="GeoFatali API",
    version=ENGINE_VERSION,
    description=(
        "Deterministic geotechnical calculations. Every response carries its method, "
        "its inputs, the standard it was run under, the engine version, the provenance "
        "of every parameter and every warning raised. No result from this API is a "
        "foundation design."
    ),
)

API = "/api/v1"

# Persistence: accounts, projects, the ground record, and the calculation
# history. The stateless calculators below remain, because a quick bearing
# check should not require an account.
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(ground.router)
app.include_router(project_calculations.router)


def _record(record: CalculationRecord) -> JSONResponse:
    return JSONResponse(record.as_dict())


def _source(name: str) -> Source:
    return Source(name)


def _soil(model) -> SoilParameters:
    return SoilParameters(
        unit_weight_kn_m3=model.unit_weight_kn_m3,
        cohesion_kpa=model.cohesion_kpa,
        friction_angle_deg=model.friction_angle_deg,
        saturated_unit_weight_kn_m3=model.saturated_unit_weight_kn_m3,
        analysis=model.analysis,
        cohesion_source=_source(model.cohesion_source),
        friction_source=_source(model.friction_source),
        unit_weight_source=_source(model.unit_weight_source),
        reference=model.reference,
    )


def _ground(model) -> GroundConditions:
    return GroundConditions(
        groundwater_depth_m=model.groundwater_depth_m,
        ground_slope_deg=model.ground_slope_deg,
        base_tilt_deg=model.base_tilt_deg,
        load_inclination_deg=model.load_inclination_deg,
        groundwater_observed=model.groundwater_observed,
    )


def _findings(model: FindingsIn) -> GroundFindings:
    return GroundFindings(**model.model_dump())


@app.exception_handler(InvalidInput)
async def _invalid_input(_request, exc: InvalidInput):
    """Impossible input is the caller's bug, so it is a 422 and it says which field."""
    return JSONResponse(
        status_code=422,
        content={"error": "INVALID_INPUT", "field": exc.field_name, "message": exc.message},
    )


@app.on_event("startup")
def _announce() -> None:
    """Say where the server can be reached, and whether the schema is ready."""
    import os

    host = os.environ.get("GEOFATALI_BIND_HOST", "")
    port = os.environ.get("GEOFATALI_PORT", "8000")
    lines = ["", "  GeoFatali API " + ENGINE_VERSION, ""]

    for address in _lan_addresses():
        lines.append(f"  On this network:  http://{address}:{port}")
    lines.append(f"  On this machine:  http://127.0.0.1:{port}")

    if host not in ("0.0.0.0", "::"):
        lines += [
            "",
            "  NOTE: if you did not start this with --host 0.0.0.0 it is listening",
            "        on this machine only, and a phone will not reach it.",
        ]

    try:
        version = current_version(db_engine())
        if version is None:
            lines += [
                "",
                "  WARNING: the database has no schema. Run:",
                "             python -m app.db.cli migrate",
            ]
        else:
            lines.append(f"  Schema:           {version}")
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        lines += ["", f"  WARNING: database unreachable ({type(exc).__name__}).",
                  "           Check DATABASE_URL."]

    lines.append("")
    print("\n".join(lines), flush=True)


@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness, plus whether the database is reachable and up to date.

    A service that answers 200 while its database is unreachable is worse than
    one that answers 503: it keeps traffic flowing to something that cannot
    store anything.
    """
    database: dict[str, Any]
    try:
        database = {"reachable": True, "schema_version": current_version(db_engine())}
    except Exception as exc:  # noqa: BLE001 - the reason is reported, not swallowed
        database = {"reachable": False, "error": type(exc).__name__}
    return {
        "status": "ok" if database["reachable"] else "degraded",
        "engine_version": ENGINE_VERSION,
        "database": database,
    }


# ───────────────────────────── reference data ─────────────────────────────

@app.get(f"{API}/reference/sectors")
def list_sectors() -> dict[str, Any]:
    """Every industry the engine screens for, and what governs each one."""
    return {
        "sectors": [
            {
                "id": s.id,
                "label": s.label,
                "summary": s.summary,
                "typical_structures": list(s.typical_structures),
                "governing_checks": [
                    {"id": c, "label": CHECKS[c].label, "why": CHECKS[c].why}
                    for c in s.governing_checks
                ],
                "candidate_foundations": list(s.candidate_foundations),
                "required_investigation": list(s.required_investigation),
                "settlement_limit_mm": s.settlement_limit_mm,
                "standards": list(s.standards),
                "note": s.note,
            }
            for s in SECTORS.values()
        ]
    }


@app.get(f"{API}/reference/standards")
def list_standards() -> dict[str, Any]:
    return {
        "standards": [
            {
                "id": s.id,
                "name": s.name,
                "edition": s.edition,
                "jurisdiction": s.jurisdiction,
                "default_bearing_fs": s.default_bearing_fs,
                "settlement_limit_mm": s.settlement_limit_mm,
                "combinations": [c.__dict__ for c in s.combinations],
                "reference": s.reference,
            }
            for s in STANDARDS.values()
        ]
    }


@app.get(f"{API}/reference/methods")
def list_methods() -> dict[str, Any]:
    """Every calculation method, with the published source behind it."""
    return {"methods": [m.__dict__ for m in METHOD_REFERENCES.values()]}


@app.get(f"{API}/reference/foundations")
def list_foundations() -> dict[str, Any]:
    return {"foundations": [f.__dict__ for f in FOUNDATION_TYPES.values()]}


# ───────────────────────────── soil ─────────────────────────────

@app.post(f"{API}/soil/classify")
def classify(request: ClassificationRequest) -> dict[str, Any]:
    result = classify_uscs(IndexTests(**request.model_dump()))
    return {
        "symbol": result.symbol,
        "name": result.name,
        "group_name": result.group_name,
        "plasticity_index": result.plasticity_index,
        "swell_potential": swell_potential(result.plasticity_index),
        "basis": result.basis,
        "warnings": result.warnings.as_list(),
    }


@app.post(f"{API}/soil/spt-correction")
def spt_correction(request: SptCorrectionRequest) -> dict[str, Any]:
    result = corr.correct_spt(**request.model_dump())
    payload = result.as_dict()
    payload["warnings"] = result.warnings.as_list()
    if result.n1_60 is not None:
        phi = corr.friction_angle_from_spt(result.n1_60)
        payload["correlations"] = {
            "friction_angle": {
                **phi.measurement.as_dict(),
                "method": phi.method,
                "citation": phi.citation,
                "warnings": phi.warnings.as_list(),
            }
        }
    return payload


@app.post(f"{API}/soil/dcp")
def dcp(request: DcpRequest) -> dict[str, Any]:
    index = corr.dcp_index(**request.model_dump())
    cbr = corr.cbr_from_dcp(index)
    return {
        "dcp_index_mm_per_blow": round(index, 2),
        "cbr": cbr.measurement.as_dict(),
        "subgrade_class": corr.subgrade_class_from_cbr(cbr.value),
        "method": cbr.method,
        "citation": cbr.citation,
        "warnings": cbr.warnings.as_list(),
    }


@app.post(f"{API}/soil/ai-observation")
def ai_observation(request: SoilAnalysisIn) -> dict[str, Any]:
    """Accept a vision-model response — and reject it if it invented a measurement."""
    try:
        observation = observation_from_payload(
            request.payload,
            model_provider=request.model_provider,
            model_name=request.model_name,
        )
    except FabricatedMeasurement as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "FABRICATED_MEASUREMENT", "message": str(exc)},
        ) from exc
    return observation.as_dict()


@app.get(f"{API}/soil/ai-prompt")
def ai_prompt() -> dict[str, str]:
    return {"system_prompt": SYSTEM_PROMPT}


# ───────────────────────────── calculations ─────────────────────────────

@app.post(f"{API}/calculations/bearing-capacity")
def calc_bearing_capacity(request: BearingCapacityRequest) -> JSONResponse:
    return _record(bearing_capacity(
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
    ))


@app.post(f"{API}/calculations/footing")
def calc_footing(request: FootingSizingRequest) -> JSONResponse:
    return _record(size_footing(
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
    ))


@app.post(f"{API}/calculations/eccentricity")
def calc_eccentricity(
    axial_load_kn: float,
    moment_knm: float,
    width_m: float,
    length_m: float | None = None,
    horizontal_load_kn: float = 0.0,
    base_friction_angle_deg: float | None = None,
    base_adhesion_kpa: float = 0.0,
) -> dict[str, Any]:
    return eccentricity_check(
        axial_load_kn=axial_load_kn,
        moment_knm=moment_knm,
        width_m=width_m,
        length_m=length_m,
        horizontal_load_kn=horizontal_load_kn,
        base_friction_angle_deg=base_friction_angle_deg,
        base_adhesion_kpa=base_adhesion_kpa,
    )


@app.post(f"{API}/calculations/settlement/elastic")
def calc_elastic_settlement(request: ElasticSettlementRequest) -> JSONResponse:
    data = request.model_dump()
    data["modulus_source"] = _source(data.pop("modulus_source"))
    data["standard_id"] = data.pop("standard")
    return _record(elastic_settlement(**data))


@app.post(f"{API}/calculations/settlement/consolidation")
def calc_consolidation(request: ConsolidationRequest) -> JSONResponse:
    data = request.model_dump()
    data["standard_id"] = data.pop("standard")
    return _record(consolidation_settlement(**data))


@app.post(f"{API}/calculations/load")
def calc_load(request: ColumnLoadRequest) -> JSONResponse:
    data = request.model_dump()
    standard_id = data.pop("standard")
    return _record(estimate_column_load(ColumnGeometry(**data), standard_id=standard_id))


@app.post(f"{API}/calculations/foundation-options")
def calc_foundation_options(request: FoundationScreeningRequest) -> JSONResponse:
    return _record(screen_foundations(ScreeningInput(
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
    )))


@app.post(f"{API}/foundations/steps")
def foundation_steps(request: StepsRequest) -> dict[str, Any]:
    """The ordered site sequence for a chosen foundation, adapted to this ground."""
    if request.foundation_type not in FOUNDATION_TYPES:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "UNKNOWN_FOUNDATION_TYPE",
                "known": sorted(FOUNDATION_TYPES),
            },
        )
    steps = construction_steps(
        request.foundation_type,
        findings=_findings(request.findings),
        sector_id=request.sector,
    )
    spec = FOUNDATION_TYPES[request.foundation_type]
    return {
        "foundation_type": spec.id,
        "label": spec.label,
        "summary": spec.summary,
        "steps": steps_as_dicts(steps),
        "hold_points": [s.order for s in steps if s.hold_point],
        "engine_version": ENGINE_VERSION,
        "note": (
            "A construction sequence, not a design. The hold points are where work "
            "must stop for inspection by a qualified engineer."
        ),
    }
