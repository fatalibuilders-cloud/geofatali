"""One-dimensional consolidation settlement, and how long it takes.

Spec section 27. This is the calculation that decides whether a building on
soft clay is a footing job or a piling job, and it is the one most often
skipped because it needs oedometer data nobody commissioned.

    Normally consolidated:  Sc = Cc  H /(1+e0) log10((s'0 + ds)/s'0)
    Over-consolidated,
      staying below s'p:    Sc = Cr  H /(1+e0) log10((s'0 + ds)/s'0)
      crossing s'p:         Sc = Cr  H /(1+e0) log10(s'p/s'0)
                               + Cc  H /(1+e0) log10((s'0 + ds)/s'p)

The stress increment ds comes from either the 2:1 approximation or the
Boussinesq solution for a loaded rectangle; the method is chosen and recorded.
"""

from __future__ import annotations

import math
from typing import Any

from ..provenance import Measurement, ProvenanceLedger, Source
from ..record import CalculationRecord, Status, insufficient_data
from ..standards import get_standard
from ..units import GAMMA_WATER_KN_M3, m_to_mm
from ..warnings import WarningList, require_non_negative, require_positive


def stress_increment_2to1(
    *, load_kn: float, width_m: float, length_m: float, depth_below_base_m: float
) -> float:
    """2:1 spread: the load disperses at one horizontal to two vertical."""
    p = require_positive("load_kn", load_kn)
    b = require_positive("width_m", width_m)
    l = require_positive("length_m", length_m)
    z = require_non_negative("depth_below_base_m", depth_below_base_m)
    return p / ((b + z) * (l + z))


def boussinesq_corner_factor(m: float, n: float) -> float:
    """Newmark's influence factor for the corner of a uniformly loaded rectangle."""
    m2, n2 = m * m, n * n
    a = 2 * m * n * math.sqrt(m2 + n2 + 1) / (m2 + n2 + 1 + m2 * n2)
    b = (m2 + n2 + 2) / (m2 + n2 + 1)
    c = 2 * m * n * math.sqrt(m2 + n2 + 1) / (m2 + n2 + 1 - m2 * n2)
    theta = math.atan(c) if (m2 + n2 + 1 - m2 * n2) > 0 else math.atan(c) + math.pi
    return (a * b + theta) / (4 * math.pi)


def stress_increment_boussinesq(
    *, pressure_kpa: float, width_m: float, length_m: float, depth_below_base_m: float
) -> float:
    """Vertical stress under the CENTRE of a loaded rectangle, by four corners."""
    q = require_positive("pressure_kpa", pressure_kpa)
    b = require_positive("width_m", width_m)
    l = require_positive("length_m", length_m)
    z = require_positive("depth_below_base_m", depth_below_base_m)
    m = (b / 2) / z
    n = (l / 2) / z
    return 4.0 * q * boussinesq_corner_factor(m, n)


def effective_stress_at(
    *, depth_m: float, unit_weight_kn_m3: float, groundwater_depth_m: float | None
) -> float:
    z = require_positive("depth_m", depth_m)
    gamma = require_positive("unit_weight_kn_m3", unit_weight_kn_m3)
    if groundwater_depth_m is None or groundwater_depth_m >= z:
        return gamma * z
    dw = require_non_negative("groundwater_depth_m", groundwater_depth_m)
    return gamma * dw + (gamma - GAMMA_WATER_KN_M3) * (z - dw)


def consolidation_settlement(
    *,
    layer_thickness_m: float,
    layer_mid_depth_m: float,
    initial_void_ratio: float | None,
    compression_index_cc: float | None,
    recompression_index_cr: float | None = None,
    preconsolidation_pressure_kpa: float | None = None,
    unit_weight_kn_m3: float,
    groundwater_depth_m: float | None,
    stress_increment_kpa: float | None = None,
    load_kn: float | None = None,
    footing_width_m: float | None = None,
    footing_length_m: float | None = None,
    footing_depth_m: float = 0.0,
    stress_method: str = "stress_2to1",
    standard_id: str | None = None,
    parameter_source: Source = Source.LABORATORY,
) -> CalculationRecord:
    """Primary consolidation settlement of one compressible layer."""
    standard = get_standard(standard_id)
    w = WarningList()
    ledger = ProvenanceLedger()

    inputs: dict[str, Any] = {
        "layer_thickness_m": layer_thickness_m,
        "layer_mid_depth_m": layer_mid_depth_m,
        "initial_void_ratio": initial_void_ratio,
        "compression_index_cc": compression_index_cc,
        "recompression_index_cr": recompression_index_cr,
        "preconsolidation_pressure_kpa": preconsolidation_pressure_kpa,
        "unit_weight_kn_m3": unit_weight_kn_m3,
        "groundwater_depth_m": groundwater_depth_m,
        "stress_increment_kpa": stress_increment_kpa,
        "stress_method": stress_method,
    }

    missing: dict[str, str] = {}
    if compression_index_cc is None:
        missing["compression_index_cc"] = (
            "Cc comes from an oedometer (one-dimensional consolidation) test to BS 1377-5 "
            "or ASTM D2435. There is no defensible substitute for a settlement-governed design."
        )
    if initial_void_ratio is None:
        missing["initial_void_ratio"] = (
            "e0 comes from the same oedometer test, or from the moisture content, specific "
            "gravity and degree of saturation."
        )
    if stress_increment_kpa is None and (load_kn is None or footing_width_m is None):
        missing["stress_increment_kpa"] = (
            "Either supply the stress increment at mid-layer directly, or supply the footing "
            "load and plan dimensions so the engine can compute it."
        )
    if missing:
        return insufficient_data(
            "consolidation_settlement", "consolidation_1d", missing,
            standard=standard, inputs=inputs,
        )

    h = require_positive("layer_thickness_m", layer_thickness_m)
    z_mid = require_positive("layer_mid_depth_m", layer_mid_depth_m)
    e0 = require_positive("initial_void_ratio", initial_void_ratio)
    cc = require_positive("compression_index_cc", compression_index_cc)

    if stress_increment_kpa is None:
        z_below = max(z_mid - footing_depth_m, 0.01)
        length = footing_length_m or footing_width_m
        if stress_method == "boussinesq_rectangle":
            pressure = load_kn / (footing_width_m * length)
            delta_sigma = stress_increment_boussinesq(
                pressure_kpa=pressure,
                width_m=footing_width_m,
                length_m=length,
                depth_below_base_m=z_below,
            )
        else:
            stress_method = "stress_2to1"
            delta_sigma = stress_increment_2to1(
                load_kn=load_kn,
                width_m=footing_width_m,
                length_m=length,
                depth_below_base_m=z_below,
            )
    else:
        delta_sigma = require_positive("stress_increment_kpa", stress_increment_kpa)

    sigma0 = effective_stress_at(
        depth_m=z_mid,
        unit_weight_kn_m3=unit_weight_kn_m3,
        groundwater_depth_m=groundwater_depth_m,
    )
    sigma_f = sigma0 + delta_sigma

    ledger.record("compression_index_cc", Measurement(cc, "-", parameter_source))
    ledger.record("initial_void_ratio", Measurement(e0, "-", parameter_source))

    sigma_p = preconsolidation_pressure_kpa
    cr = recompression_index_cr
    if sigma_p is None:
        w.warn(
            "ASSUMED_NORMALLY_CONSOLIDATED",
            "No preconsolidation pressure was supplied, so the layer was treated as normally "
            "consolidated. This is the conservative assumption — it gives the largest "
            "settlement — but an over-consolidated clay may settle several times less.",
            "preconsolidation_pressure_kpa",
        )
        state = "normally_consolidated"
        settlement_m = (cc * h / (1 + e0)) * math.log10(sigma_f / sigma0)
    else:
        sigma_p = require_positive("preconsolidation_pressure_kpa", sigma_p)
        if cr is None:
            cr = cc / 6.0
            w.warn(
                "ASSUMED_RECOMPRESSION_INDEX",
                "Cr was not supplied, so Cc/6 was used — the middle of the Cc/5 to Cc/10 band "
                "reported in the literature. Read Cr off the unload-reload loop of the "
                "oedometer test where the clay is over-consolidated.",
                "recompression_index_cr",
            )
            ledger.record("recompression_index_cr", Measurement(cr, "-", Source.ESTIMATED))
        else:
            ledger.record("recompression_index_cr", Measurement(cr, "-", parameter_source))

        if sigma_p <= sigma0 * 1.02:
            state = "normally_consolidated"
            settlement_m = (cc * h / (1 + e0)) * math.log10(sigma_f / sigma0)
        elif sigma_f <= sigma_p:
            state = "over_consolidated_recompression_only"
            settlement_m = (cr * h / (1 + e0)) * math.log10(sigma_f / sigma0)
            w.info(
                "STAYS_BELOW_PRECONSOLIDATION",
                f"The final stress ({sigma_f:.0f} kPa) stays below the preconsolidation "
                f"pressure ({sigma_p:.0f} kPa), so the clay recompresses only and the "
                "settlement is small.",
            )
        else:
            state = "over_consolidated_crossing"
            settlement_m = (cr * h / (1 + e0)) * math.log10(sigma_p / sigma0) + (
                cc * h / (1 + e0)
            ) * math.log10(sigma_f / sigma_p)
            w.warn(
                "CROSSES_PRECONSOLIDATION",
                f"The load takes the clay past its preconsolidation pressure "
                f"({sigma_p:.0f} kPa). Beyond that point it compresses on the virgin curve "
                "and settlement increases sharply — reducing the bearing pressure to stay "
                "below sigma'p is often the cheapest fix available.",
            )

    settlement_mm = m_to_mm(settlement_m)
    if settlement_mm > standard.settlement_limit_mm:
        w.warn(
            "SETTLEMENT_EXCEEDS_LIMIT",
            f"Consolidation settlement of {settlement_mm:.0f} mm exceeds the "
            f"{standard.settlement_limit_mm:.0f} mm limit usually applied to framed buildings. "
            "Consider a raft, ground improvement, preloading, or piling through the layer.",
        )
    if delta_sigma / sigma0 < 0.1:
        w.info(
            "SMALL_STRESS_INCREMENT",
            "The stress increment at mid-layer is under 10% of the existing effective stress, "
            "so this layer contributes little; the layers nearer the footing govern.",
        )

    return CalculationRecord(
        calculation_type="consolidation_settlement",
        method="consolidation_1d",
        status=Status.CALCULATED,
        inputs=inputs,
        results={
            "settlement_mm": round(settlement_mm, 1),
            "initial_effective_stress_kpa": round(sigma0, 1),
            "stress_increment_kpa": round(delta_sigma, 1),
            "final_effective_stress_kpa": round(sigma_f, 1),
            "state": state,
            "stress_method": stress_method,
        },
        warnings=w,
        provenance=ledger,
        standard_id=standard.id,
        standard_edition=standard.edition,
    )


def secondary_compression(
    *,
    secondary_index_c_alpha: float,
    layer_thickness_m: float,
    void_ratio_end_primary: float,
    time_start_years: float,
    time_end_years: float,
) -> float:
    """Creep settlement after primary consolidation ends, in mm.

    Ss = (C_alpha / (1 + e_p)) H log10(t2/t1). Matters for peat, organic clay
    and soft normally-consolidated clay, and is negligible for sand.
    """
    ca = require_positive("secondary_index_c_alpha", secondary_index_c_alpha)
    h = require_positive("layer_thickness_m", layer_thickness_m)
    ep = require_positive("void_ratio_end_primary", void_ratio_end_primary)
    t1 = require_positive("time_start_years", time_start_years)
    t2 = require_positive("time_end_years", time_end_years)
    if t2 <= t1:
        return 0.0
    return m_to_mm((ca / (1 + ep)) * h * math.log10(t2 / t1))


def time_factor_for_degree(degree_of_consolidation: float) -> float:
    """Terzaghi's time factor Tv for an average degree of consolidation U."""
    u = require_positive("degree_of_consolidation", degree_of_consolidation)
    if u >= 1.0:
        raise ValueError("Consolidation is asymptotic: U = 100% is never reached in finite time")
    if u <= 0.6:
        return (math.pi / 4.0) * u**2
    return 1.781 - 0.933 * math.log10(100.0 * (1.0 - u))


def consolidation_time_years(
    *,
    degree_of_consolidation: float,
    drainage_path_m: float,
    cv_m2_per_year: float,
) -> float:
    """t = Tv H_dr^2 / cv. Double-drained layers use half the thickness."""
    tv = time_factor_for_degree(degree_of_consolidation)
    h = require_positive("drainage_path_m", drainage_path_m)
    cv = require_positive("cv_m2_per_year", cv_m2_per_year)
    return tv * h * h / cv
