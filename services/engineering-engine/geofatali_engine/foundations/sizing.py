"""Sizing a shallow foundation, and checking it under eccentric load.

Spec sections 25-26. The naive form of this is one line:

    A_required = P / q_allow

but ``q_allow`` is itself a function of the footing width, through both the
self-weight term and the shape and depth factors. Sizing a footing from a
bearing capacity computed at an assumed width and then not going back is a
standard way to end up 20% wrong on a wide footing in sand, so this module
iterates to convergence and reports how many iterations it took.
"""

from __future__ import annotations

import math
from typing import Any

from ..bearing.capacity import (
    Footing,
    GroundConditions,
    SoilParameters,
    bearing_capacity,
)
from ..provenance import Measurement, ProvenanceLedger, Source
from ..record import CalculationRecord, Status
from ..standards import get_standard
from ..warnings import InvalidInput, WarningList, require_positive

#: Buildable increments. A footing is set out on site with a tape, so 2.37 m
#: is not a footing width — 2.40 m is.
SIZE_INCREMENT_M = 0.05

MAX_ITERATIONS = 40
CONVERGENCE_M = 0.005


def _round_up_to_increment(value_m: float) -> float:
    return math.ceil(value_m / SIZE_INCREMENT_M) * SIZE_INCREMENT_M


def size_footing(
    *,
    service_load_kn: float,
    soil: SoilParameters,
    depth_m: float,
    shape: str = "square",
    length_over_width: float = 1.0,
    ground: GroundConditions | None = None,
    method: str = "vesic",
    factor_of_safety: float | None = None,
    standard_id: str | None = None,
    max_width_m: float = 6.0,
) -> CalculationRecord:
    """Find the smallest buildable footing that carries the load.

    ``service_load_kn`` is the column load for a pad, or the load per metre
    run for a strip footing (in which case pass ``shape="strip"``).
    """
    standard = get_standard(standard_id)
    ground = ground or GroundConditions()
    w = WarningList()
    ledger = ProvenanceLedger()
    p = require_positive("service_load_kn", service_load_kn)
    require_positive("depth_m", depth_m)
    if length_over_width < 1.0:
        raise InvalidInput("length_over_width", "must be 1.0 or more (L is the longer side)")

    inputs: dict[str, Any] = {
        "service_load_kn": p,
        "depth_m": depth_m,
        "shape": shape,
        "length_over_width": length_over_width,
        "method": method,
        "factor_of_safety": factor_of_safety or standard.default_bearing_fs,
    }

    def capacity_at(width: float) -> CalculationRecord:
        length = None if shape in ("square", "circular", "strip") else width * length_over_width
        return bearing_capacity(
            soil=soil,
            footing=Footing(width_m=width, depth_m=depth_m, length_m=length, shape=shape),
            ground=ground,
            method=method,
            factor_of_safety=factor_of_safety,
            standard_id=standard_id,
        )

    # The first pass needs a bearing capacity to divide by, so it starts from a
    # trial width and converges from there. The trial value only affects how
    # many iterations are needed, never the answer.
    width = 1.0
    iterations = 0
    last_capacity: CalculationRecord | None = None
    converged = False

    while iterations < MAX_ITERATIONS:
        iterations += 1
        cap = capacity_at(width)
        if cap.status is not Status.CALCULATED:
            # Propagate the refusal unchanged — sizing cannot fix missing soil data.
            cap.calculation_type = "footing_sizing"
            return cap
        last_capacity = cap
        q_allow_net = cap.results["net_allowable_capacity_kpa"]
        if q_allow_net <= 0:
            w.critical(
                "NO_ALLOWABLE_CAPACITY",
                "The net allowable bearing pressure is zero or negative at this depth. The "
                "ground cannot carry a shallow foundation here as modelled.",
            )
            break

        if shape == "strip":
            required_width = p / q_allow_net          # kN/m over kPa gives metres
        elif shape == "circular":
            required_width = math.sqrt(4.0 * p / (math.pi * q_allow_net))
        elif shape == "square":
            required_width = math.sqrt(p / q_allow_net)
        else:
            required_width = math.sqrt(p / (q_allow_net * length_over_width))

        if abs(required_width - width) <= CONVERGENCE_M:
            width = required_width
            converged = True
            break
        # Damped update keeps the iteration stable when capacity grows with width.
        width = width + 0.7 * (required_width - width)
        if width > max_width_m:
            width = max_width_m
            break

    if not converged and iterations >= MAX_ITERATIONS:
        w.warn(
            "SIZING_DID_NOT_CONVERGE",
            f"Footing width did not settle within {MAX_ITERATIONS} iterations. Treat the "
            "result as indicative and check it by hand.",
        )

    final_width = _round_up_to_increment(width)
    if final_width >= max_width_m:
        w.warn(
            "FOOTING_TOO_LARGE",
            f"The required footing is {final_width:.2f} m wide, at or beyond the {max_width_m:.1f} m "
            "limit set for this screening. Once pads approach half the column spacing they "
            "overlap: a raft is then both cheaper and stiffer.",
            "width_m",
        )

    final = capacity_at(final_width)
    if final.status is not Status.CALCULATED:
        final.calculation_type = "footing_sizing"
        return final

    length = (
        final_width
        if shape in ("square", "circular", "strip")
        else final_width * length_over_width
    )
    area = (
        final_width
        if shape == "strip"
        else math.pi * final_width**2 / 4.0
        if shape == "circular"
        else final_width * length
    )
    applied = p / area
    q_allow_net = final.results["net_allowable_capacity_kpa"]
    utilisation = applied / q_allow_net if q_allow_net > 0 else math.inf

    w.extend(final.warnings)
    ledger.entries.update(final.provenance.entries)
    ledger.record("service_load_kn", Measurement(p, "kN", Source.ESTIMATED))

    if utilisation > 1.0:
        w.critical(
            "BEARING_EXCEEDED",
            f"Applied pressure {applied:.0f} kPa exceeds the net allowable "
            f"{q_allow_net:.0f} kPa at the chosen size. Increase the footing, deepen it, or "
            "move to a different foundation system.",
        )
    if final_width < 0.6:
        w.info(
            "MINIMUM_PRACTICAL_WIDTH",
            "The calculated width is below the 0.6 m that is normally the practical minimum "
            "for an excavated and reinforced footing. Detailing, not bearing, will govern.",
        )

    return CalculationRecord(
        calculation_type="footing_sizing",
        method=method,
        status=Status.CALCULATED,
        inputs=inputs,
        results={
            "width_m": round(final_width, 2),
            "length_m": round(length, 2) if shape != "strip" else None,
            "depth_m": depth_m,
            "shape": shape,
            "area_m2": round(area, 3),
            "applied_pressure_kpa": round(applied, 1),
            "net_allowable_capacity_kpa": q_allow_net,
            "gross_allowable_capacity_kpa": final.results["gross_allowable_capacity_kpa"],
            "utilisation": round(utilisation, 3),
            "iterations": iterations,
            "converged": converged,
            "bearing_calculation": final.as_dict(),
        },
        warnings=w,
        provenance=ledger,
        standard_id=standard.id,
        standard_edition=standard.edition,
    )


def eccentricity_check(
    *,
    axial_load_kn: float,
    moment_knm: float,
    width_m: float,
    length_m: float | None = None,
    horizontal_load_kn: float = 0.0,
    base_friction_angle_deg: float | None = None,
    base_adhesion_kpa: float = 0.0,
) -> dict[str, Any]:
    """Pressure distribution under an eccentrically loaded rectangular footing.

    Within the middle third (e <= B/6) the whole base stays in compression:

        q_max = P/A (1 + 6e/B),  q_min = P/A (1 - 6e/B)

    Outside it, part of the base lifts off and those equations stop being
    true. The engine switches to the partial-contact form

        q_max = 2P / (3 L (B/2 - e))

    rather than returning a negative minimum pressure and letting the caller
    think the soil is pulling the footing down. Spec section 26 warns against
    exactly this.
    """
    p = require_positive("axial_load_kn", axial_load_kn)
    b = require_positive("width_m", width_m)
    length = length_m if length_m else b
    require_positive("length_m", length)
    if moment_knm < 0:
        raise InvalidInput("moment_knm", "supply the magnitude; sign is not meaningful here")

    area = b * length
    e = moment_knm / p
    middle_third = e <= b / 6.0
    effective_width = max(b - 2.0 * e, 0.0)

    if middle_third:
        q_max = (p / area) * (1.0 + 6.0 * e / b)
        q_min = (p / area) * (1.0 - 6.0 * e / b)
        contact = 1.0
        regime = "full_contact"
    elif e < b / 2.0:
        q_max = 2.0 * p / (3.0 * length * (b / 2.0 - e))
        q_min = 0.0
        contact = 3.0 * (b / 2.0 - e) / b
        regime = "partial_contact"
    else:
        q_max = math.inf
        q_min = 0.0
        contact = 0.0
        regime = "unstable"

    result: dict[str, Any] = {
        "eccentricity_m": round(e, 4),
        "middle_third_limit_m": round(b / 6.0, 4),
        "within_middle_third": middle_third,
        "regime": regime,
        "q_max_kpa": None if math.isinf(q_max) else round(q_max, 1),
        "q_min_kpa": round(q_min, 1),
        "base_in_contact_fraction": round(contact, 3),
        "effective_width_m": round(effective_width, 3),
        "effective_area_m2": round(effective_width * length, 3),
        "overturning_factor_of_safety": round((b / 2.0) / e, 2) if e > 0 else None,
    }

    if horizontal_load_kn > 0:
        phi = base_friction_angle_deg
        if phi is None:
            result["sliding"] = {
                "status": "INSUFFICIENT_DATA",
                "reason": (
                    "Base friction angle was not supplied, so sliding resistance cannot be "
                    "checked. Use the soil's phi' for a cast-against-ground base, or two "
                    "thirds of it for a precast base on a blinding layer."
                ),
            }
        else:
            resistance = p * math.tan(math.radians(phi)) + base_adhesion_kpa * area
            result["sliding"] = {
                "status": "CALCULATED",
                "resistance_kn": round(resistance, 1),
                "applied_kn": round(horizontal_load_kn, 1),
                "factor_of_safety": round(resistance / horizontal_load_kn, 2),
                "adequate": resistance / horizontal_load_kn >= 1.5,
                "note": "A factor of safety of 1.5 against sliding is the usual requirement.",
            }

    return result
