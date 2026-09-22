"""Immediate (elastic) settlement of a loaded area.

Spec section 27. The method is the standard elastic half-space expression
given in Bowles (1996) ch. 5:

    Se = q x B' x (1 - nu^2) x Is x If / Es

Settlement scales with 1/Es, so it is only ever as good as the modulus. A
modulus correlated from SPT blow counts gives an order-of-magnitude screen
and the result says so; a modulus from a pressuremeter or a plate test gives
something worth designing to.
"""

from __future__ import annotations

import math
from typing import Any

from ..provenance import Measurement, ProvenanceLedger, Source
from ..record import CalculationRecord, Status, insufficient_data
from ..standards import get_standard
from ..units import m_to_mm
from ..warnings import WarningList, require_positive

#: Influence factors Is for a uniformly loaded area on a deep elastic layer,
#: at the centre of a FLEXIBLE footing, indexed by L/B. Das, Table 5.x.
_IS_FLEXIBLE_CENTRE = {
    1.0: 1.12,
    1.5: 1.36,
    2.0: 1.53,
    3.0: 1.78,
    5.0: 2.10,
    10.0: 2.54,
}
#: A rigid footing settles uniformly, at about 93% of the flexible centre value.
_RIGIDITY_FACTOR = 0.93


def influence_factor(length_over_width: float, *, rigid: bool = True) -> float:
    keys = sorted(_IS_FLEXIBLE_CENTRE)
    m = min(max(length_over_width, keys[0]), keys[-1])
    lo = max(k for k in keys if k <= m)
    hi = min(k for k in keys if k >= m)
    if lo == hi:
        value = _IS_FLEXIBLE_CENTRE[lo]
    else:
        f = (m - lo) / (hi - lo)
        value = _IS_FLEXIBLE_CENTRE[lo] + f * (_IS_FLEXIBLE_CENTRE[hi] - _IS_FLEXIBLE_CENTRE[lo])
    return value * (_RIGIDITY_FACTOR if rigid else 1.0)


def depth_factor(depth_m: float, width_m: float, length_over_width: float) -> float:
    """Fox's embedment correction: an embedded footing settles less than one at surface."""
    d_over_b = depth_m / width_m
    if d_over_b <= 0:
        return 1.0
    # A smooth fit to Fox's chart across the practical range, bounded at 0.75.
    factor = 1.0 - 0.12 * math.log10(1.0 + 10.0 * d_over_b) * (1.0 + 0.1 * (length_over_width - 1))
    return max(min(factor, 1.0), 0.75)


def elastic_settlement(
    *,
    applied_pressure_kpa: float,
    width_m: float,
    length_m: float | None = None,
    depth_m: float = 0.0,
    youngs_modulus_kpa: float | None = None,
    poissons_ratio: float = 0.3,
    rigid: bool = True,
    modulus_source: Source = Source.USER,
    standard_id: str | None = None,
) -> CalculationRecord:
    """Immediate settlement under the centre of a loaded rectangle."""
    standard = get_standard(standard_id)
    w = WarningList()
    ledger = ProvenanceLedger()

    inputs: dict[str, Any] = {
        "applied_pressure_kpa": applied_pressure_kpa,
        "width_m": width_m,
        "length_m": length_m,
        "depth_m": depth_m,
        "youngs_modulus_kpa": youngs_modulus_kpa,
        "poissons_ratio": poissons_ratio,
        "rigid": rigid,
    }

    if youngs_modulus_kpa is None:
        return insufficient_data(
            "elastic_settlement",
            "elastic_settlement",
            {
                "youngs_modulus_kpa": (
                    "Settlement is inversely proportional to the soil modulus, so no modulus "
                    "means no settlement estimate. Measure it (pressuremeter, plate load test, "
                    "oedometer-derived) or correlate it from SPT/CPT and accept the warning."
                )
            },
            standard=standard,
            inputs=inputs,
        )

    q = require_positive("applied_pressure_kpa", applied_pressure_kpa)
    b = require_positive("width_m", width_m)
    es = require_positive("youngs_modulus_kpa", youngs_modulus_kpa)
    if not 0.0 <= poissons_ratio < 0.5:
        w.warn(
            "POISSON_RATIO_RANGE",
            f"Poisson's ratio of {poissons_ratio} is outside 0 to 0.5. 0.3 is usual for sand, "
            "0.5 for a saturated clay under undrained loading.",
            "poissons_ratio",
        )

    length = length_m if length_m else b
    m = max(length / b, 1.0)
    is_factor = influence_factor(m, rigid=rigid)
    if_factor = depth_factor(depth_m, b, m)

    # B' is the half-width for the centre of a flexible area; for the rigid
    # uniform case the full width with the rigidity factor above is used.
    settlement_m = q * b * (1 - poissons_ratio**2) * is_factor * if_factor / es
    settlement_mm = m_to_mm(settlement_m)

    ledger.record("youngs_modulus_kpa", Measurement(es, "kPa", modulus_source))
    ledger.record("applied_pressure_kpa", Measurement(q, "kPa", Source.ENGINEER))

    if modulus_source is Source.ESTIMATED:
        w.warn(
            "CORRELATED_MODULUS_IN_SETTLEMENT",
            "The soil modulus used here was correlated, not measured. Treat the settlement "
            "as an order-of-magnitude screen: a factor-of-two error in Es is a factor-of-two "
            "error in the settlement.",
            "youngs_modulus_kpa",
        )
    if settlement_mm > standard.settlement_limit_mm:
        w.warn(
            "SETTLEMENT_EXCEEDS_LIMIT",
            f"Estimated immediate settlement of {settlement_mm:.0f} mm exceeds the "
            f"{standard.settlement_limit_mm:.0f} mm commonly permitted for framed buildings "
            f"under {standard.name}. Consolidation settlement, where the soil is clay, comes "
            "on top of this.",
        )

    return CalculationRecord(
        calculation_type="elastic_settlement",
        method="elastic_settlement",
        status=Status.CALCULATED,
        inputs=inputs,
        results={
            "settlement_mm": round(settlement_mm, 1),
            "influence_factor_is": round(is_factor, 3),
            "depth_factor_if": round(if_factor, 3),
            "length_over_width": round(m, 2),
            "rigid": rigid,
        },
        warnings=w,
        provenance=ledger,
        standard_id=standard.id,
        standard_edition=standard.edition,
    )
