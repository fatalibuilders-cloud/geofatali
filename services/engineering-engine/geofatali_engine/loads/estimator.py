"""Preliminary building loads.

Spec sections 20-21. Two modes, and the difference between them is stated on
every output:

  Mode A  the user supplies the column load from a structural model. The
          geotechnical work then rests on a real analysis.
  Mode B  the engine estimates it from geometry and occupancy. Useful for
          screening a site before a structural engineer is appointed, and
          never to be presented as a design load.

The estimator builds Gk (permanent) and Qk (variable) separately, because the
load combination that follows depends on the design standard and cannot be
applied to a single lumped number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..provenance import Measurement, ProvenanceLedger, Source
from ..record import CalculationRecord, Status
from ..standards import get_standard
from ..warnings import InvalidInput, WarningList, require_positive

#: Self-weight of a reinforced concrete suspended slab, kN/m2 per mm of depth.
CONCRETE_UNIT_WEIGHT_KN_M3 = 25.0

#: Typical permanent superimposed loads, kN/m2 (finishes, screed, ceiling,
#: services). Ordinary values from EN 1991-1-1 Annex A practice.
SUPERIMPOSED_DEAD_KN_M2 = {
    "residential": 1.5,
    "office": 2.0,
    "retail": 2.5,
    "school": 2.0,
    "hospital": 2.5,
    "hotel": 1.8,
    "warehouse": 1.5,
    "factory": 3.0,
    "car_park": 1.0,
    "roof": 0.75,
}

#: Imposed (variable) loads, kN/m2, after EN 1991-1-1 Table 6.2 categories.
IMPOSED_LOAD_KN_M2 = {
    "residential": 2.0,     # Category A
    "office": 3.0,          # Category B
    "retail": 4.0,          # Category D1
    "school": 3.0,          # Category C1
    "hospital": 3.0,        # Category C1/C5 for wards
    "hotel": 2.0,           # Category A
    "warehouse": 7.5,       # Category E, storage — governs
    "factory": 5.0,         # Category E
    "car_park": 2.5,        # Category F
    "roof": 0.6,            # Category H, maintenance access only
}

#: Slab thicknesses that go with a span, mm — span/28 for a continuous
#: two-way slab, rounded to a buildable thickness.
def typical_slab_thickness_mm(span_m: float) -> float:
    t = (span_m * 1000.0) / 28.0
    return max(125.0, round(t / 25.0) * 25.0)


#: Wall self-weight, kN/m2 of wall elevation.
WALL_LOAD_KN_M2 = {
    "concrete_block_200": 4.2,
    "concrete_block_150": 3.2,
    "natural_stone_200": 5.5,
    "brick_230": 4.6,
    "lightweight_partition": 1.0,
    "curtain_wall": 0.8,
    "none": 0.0,
}

#: Roof build-up self-weight, kN/m2 on plan.
ROOF_LOAD_KN_M2 = {
    "iron_sheets": 0.35,
    "tiles": 0.75,
    "concrete_flat": 5.0,
    "steel_deck": 0.5,
}

OCCUPANCIES = tuple(IMPOSED_LOAD_KN_M2)


@dataclass(frozen=True)
class ColumnGeometry:
    """One internal column's share of the floors above it."""

    tributary_width_m: float
    tributary_length_m: float
    floors: int
    floor_height_m: float = 3.0
    occupancy: str = "residential"
    roof_type: str = "iron_sheets"
    wall_type: str = "none"
    #: Fraction of the tributary perimeter that carries wall. 0 for a purely
    #: internal column in a framed building.
    wall_length_m: float = 0.0
    column_size_m: float = 0.3
    slab_thickness_mm: float | None = None
    beam_allowance_kn_m2: float = 1.5

    @property
    def tributary_area_m2(self) -> float:
        return self.tributary_width_m * self.tributary_length_m


@dataclass
class LoadBreakdown:
    lines: list[tuple[str, str, float]] = field(default_factory=list)

    def add(self, name: str, kind: str, value_kn: float) -> None:
        self.lines.append((name, kind, value_kn))

    def total(self, kind: str) -> float:
        return sum(v for _, k, v in self.lines if k == kind)

    def as_list(self) -> list[dict[str, Any]]:
        return [
            {"item": n, "kind": k, "load_kn": round(v, 1)} for n, k, v in self.lines
        ]


def estimate_column_load(
    geometry: ColumnGeometry, *, standard_id: str | None = None
) -> CalculationRecord:
    """Preliminary service load on one column, built up floor by floor.

    Every contribution is listed separately so a structural engineer can see
    what was counted and, just as importantly, that nothing was counted twice
    — the slab, beams, walls, finishes and imposed load each appear once per
    floor, and the roof replaces the floor build-up at the top level.
    """
    standard = get_standard(standard_id)
    w = WarningList()
    ledger = ProvenanceLedger()
    b = LoadBreakdown()

    if geometry.occupancy not in IMPOSED_LOAD_KN_M2:
        raise InvalidInput(
            "occupancy", f"must be one of {list(OCCUPANCIES)} (got {geometry.occupancy!r})"
        )
    if geometry.roof_type not in ROOF_LOAD_KN_M2:
        raise InvalidInput(
            "roof_type", f"must be one of {list(ROOF_LOAD_KN_M2)} (got {geometry.roof_type!r})"
        )
    if geometry.wall_type not in WALL_LOAD_KN_M2:
        raise InvalidInput(
            "wall_type", f"must be one of {list(WALL_LOAD_KN_M2)} (got {geometry.wall_type!r})"
        )
    if geometry.floors < 1:
        raise InvalidInput("floors", f"must be at least 1 (got {geometry.floors})")
    area = require_positive("tributary_area_m2", geometry.tributary_area_m2)

    span = max(geometry.tributary_width_m, geometry.tributary_length_m)
    slab_mm = geometry.slab_thickness_mm or typical_slab_thickness_mm(span)
    slab_kn_m2 = CONCRETE_UNIT_WEIGHT_KN_M3 * (slab_mm / 1000.0)

    suspended_floors = max(geometry.floors - 1, 0)
    sdl = SUPERIMPOSED_DEAD_KN_M2[geometry.occupancy]
    imposed = IMPOSED_LOAD_KN_M2[geometry.occupancy]

    if suspended_floors:
        b.add(f"Slab self-weight, {slab_mm:.0f} mm x {suspended_floors} floors", "Gk",
              slab_kn_m2 * area * suspended_floors)
        b.add(f"Beams allowance x {suspended_floors} floors", "Gk",
              geometry.beam_allowance_kn_m2 * area * suspended_floors)
        b.add(f"Finishes, ceiling and services x {suspended_floors} floors", "Gk",
              sdl * area * suspended_floors)
        b.add(f"Imposed load ({geometry.occupancy}) x {suspended_floors} floors", "Qk",
              imposed * area * suspended_floors)

    # Ground floor slab is normally ground-bearing and does not reach the column.
    b.add("Ground floor slab", "Gk", 0.0)

    b.add("Roof structure and covering", "Gk", ROOF_LOAD_KN_M2[geometry.roof_type] * area)
    b.add("Roof imposed (maintenance access)", "Qk", IMPOSED_LOAD_KN_M2["roof"] * area)

    if geometry.wall_length_m > 0 and geometry.wall_type != "none":
        wall_area = geometry.wall_length_m * geometry.floor_height_m * geometry.floors
        b.add(
            f"Walls, {geometry.wall_type} over {geometry.floors} floors",
            "Gk",
            WALL_LOAD_KN_M2[geometry.wall_type] * wall_area,
        )

    column_volume = geometry.column_size_m**2 * geometry.floor_height_m * geometry.floors
    b.add("Column self-weight", "Gk", CONCRETE_UNIT_WEIGHT_KN_M3 * column_volume)

    gk = b.total("Gk")
    qk = b.total("Qk")

    # Imposed-load reduction for the number of floors carried (EN 1991-1-1
    # 6.3.1.2(11)): alpha_n = (2 + (n - 2) psi0) / n for n storeys.
    psi0 = 0.7
    n = suspended_floors
    reduction = 1.0
    if n > 2:
        reduction = (2 + (n - 2) * psi0) / n
        w.info(
            "IMPOSED_LOAD_REDUCTION",
            f"A multi-storey imposed-load reduction of {reduction:.2f} was applied over "
            f"{n} suspended floors, after EN 1991-1-1 6.3.1.2(11). Not every floor is fully "
            "loaded at the same moment.",
        )
        qk = qk * reduction

    service_combo = standard.service_combination
    uls_combo = standard.ultimate_combination
    service = gk * service_combo.gamma_g + qk * service_combo.gamma_q
    factored = gk * uls_combo.gamma_g + qk * uls_combo.gamma_q

    ledger.record("tributary_area_m2", Measurement(area, "m2", Source.USER))
    ledger.record("estimated_service_load_kn", Measurement(service, "kN", Source.ESTIMATED))

    w.warn(
        "PRELIMINARY_LOAD_ESTIMATE",
        "This column load was estimated from geometry and standard occupancy loads, not from "
        "a structural analysis. It is for screening a foundation option. Replace it with the "
        "reaction from the structural model before any footing is sized for construction.",
        "service_load_kn",
    )
    if geometry.floors > 6:
        w.warn(
            "TALL_BUILDING_ESTIMATE",
            f"At {geometry.floors} storeys, wind and frame action redistribute column loads "
            "substantially and a simple tributary-area build-up understates the worst column. "
            "Use analysed reactions.",
            "floors",
        )

    return CalculationRecord(
        calculation_type="column_load_estimate",
        method="tributary_area_buildup",
        status=Status.CALCULATED,
        inputs={
            "tributary_width_m": geometry.tributary_width_m,
            "tributary_length_m": geometry.tributary_length_m,
            "floors": geometry.floors,
            "floor_height_m": geometry.floor_height_m,
            "occupancy": geometry.occupancy,
            "roof_type": geometry.roof_type,
            "wall_type": geometry.wall_type,
            "wall_length_m": geometry.wall_length_m,
            "slab_thickness_mm": slab_mm,
        },
        results={
            "tributary_area_m2": round(area, 2),
            "permanent_gk_kn": round(gk, 1),
            "variable_qk_kn": round(qk, 1),
            "imposed_reduction_factor": round(reduction, 3),
            "service_load_kn": round(service, 1),
            "factored_load_kn": round(factored, 1),
            "service_combination": service_combo.name,
            "factored_combination": uls_combo.name,
            "breakdown": b.as_list(),
            "mode": "B_estimated",
        },
        warnings=w,
        provenance=ledger,
        standard_id=standard.id,
        standard_edition=standard.edition,
    )


def wall_load_per_metre(
    *,
    floors: int,
    floor_height_m: float,
    wall_type: str,
    slab_span_m: float,
    occupancy: str = "residential",
    roof_type: str = "iron_sheets",
) -> dict[str, float]:
    """Preliminary load per metre run on a load-bearing wall, kN/m.

    This is what a strip footing is sized on, and it is the common case for
    single- and two-storey masonry construction across East Africa.
    """
    if wall_type not in WALL_LOAD_KN_M2:
        raise InvalidInput("wall_type", f"must be one of {list(WALL_LOAD_KN_M2)}")
    if occupancy not in IMPOSED_LOAD_KN_M2:
        raise InvalidInput("occupancy", f"must be one of {list(OCCUPANCIES)}")
    require_positive("slab_span_m", slab_span_m)
    if floors < 1:
        raise InvalidInput("floors", "must be at least 1")

    half_span = slab_span_m / 2.0
    suspended = max(floors - 1, 0)
    slab_mm = typical_slab_thickness_mm(slab_span_m)

    gk = WALL_LOAD_KN_M2[wall_type] * floor_height_m * floors
    gk += (CONCRETE_UNIT_WEIGHT_KN_M3 * slab_mm / 1000.0 + SUPERIMPOSED_DEAD_KN_M2[occupancy]) \
        * half_span * suspended
    gk += ROOF_LOAD_KN_M2[roof_type] * half_span

    qk = IMPOSED_LOAD_KN_M2[occupancy] * half_span * suspended
    qk += IMPOSED_LOAD_KN_M2["roof"] * half_span

    return {
        "permanent_gk_kn_per_m": round(gk, 1),
        "variable_qk_kn_per_m": round(qk, 1),
        "service_load_kn_per_m": round(gk + qk, 1),
        "assumed_slab_thickness_mm": slab_mm,
    }
