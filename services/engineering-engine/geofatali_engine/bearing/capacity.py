"""Bearing capacity of a shallow foundation.

The centre of the product. Everything upstream (photographs, boreholes, SPT,
laboratory work) exists to put defensible numbers into this calculation, and
everything downstream (footing sizing, foundation screening, the report)
reads its output.

    q_ult = c Nc sc dc ic gc bc
          + q Nq sq dq iq gq bq
          + 0.5 gamma' B N_gamma s_gamma d_gamma i_gamma g_gamma b_gamma

with the water table handled properly in both the surcharge term ``q`` and
the effective unit weight in the self-weight term.

Two things this module will not do:

1. Invent a soil parameter. No cohesion and no friction angle means
   ``INSUFFICIENT_DATA``, not a "typical value for clay".
2. Mix methods. The chosen method supplies its own N-gamma and its own
   correction factors, end to end.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..provenance import Measurement, ProvenanceLedger, Source
from ..record import CalculationRecord, Status, insufficient_data
from ..standards import Standard, get_standard
from ..units import GAMMA_WATER_KN_M3
from ..warnings import (
    InvalidInput,
    WarningList,
    require_friction_angle,
    require_non_negative,
    require_positive,
)
from .factors import (
    TERZAGHI_SHAPE_COEFFICIENTS,
    BearingFactors,
    CorrectionFactors,
    bearing_factors,
    hansen_vesic_factors,
    meyerhof_factors,
)

SHAPES = ("strip", "square", "rectangular", "circular")


@dataclass(frozen=True)
class SoilParameters:
    """The founding stratum, as effective or total stress parameters.

    Analysis type matters and is explicit:
      * ``drained``   — c' and phi', long-term, the normal case for sand.
      * ``undrained`` — Cu with phi = 0, short-term, the governing case for
        a clay loaded quickly.
    A clay usually needs both checks; the engine runs whichever it is told to
    and the screening engine asks for both.
    """

    unit_weight_kn_m3: float
    cohesion_kpa: float | None = None
    friction_angle_deg: float | None = None
    saturated_unit_weight_kn_m3: float | None = None
    analysis: str = "drained"
    #: Where each parameter came from, for the provenance ledger.
    cohesion_source: Source = Source.USER
    friction_source: Source = Source.USER
    unit_weight_source: Source = Source.USER
    reference: str | None = None

    @property
    def gamma_sat(self) -> float:
        # Saturated unit weight is commonly 1-2 kN/m3 above bulk; where it was
        # not measured the bulk value is used and the caller is warned rather
        # than the engine inventing an increment.
        return self.saturated_unit_weight_kn_m3 or self.unit_weight_kn_m3


@dataclass(frozen=True)
class Footing:
    width_m: float
    depth_m: float
    length_m: float | None = None
    shape: str = "rectangular"

    @property
    def effective_length(self) -> float:
        if self.shape in ("square", "circular"):
            return self.width_m
        if self.shape == "strip":
            return math.inf
        return self.length_m if self.length_m else self.width_m

    @property
    def b_over_l(self) -> float:
        el = self.effective_length
        return 0.0 if math.isinf(el) else self.width_m / el

    @property
    def area_m2(self) -> float:
        if self.shape == "circular":
            return math.pi * self.width_m**2 / 4.0
        if self.shape == "strip":
            return self.width_m  # per metre run
        return self.width_m * self.effective_length


@dataclass(frozen=True)
class GroundConditions:
    groundwater_depth_m: float | None = None
    ground_slope_deg: float = 0.0
    base_tilt_deg: float = 0.0
    load_inclination_deg: float = 0.0
    #: True when the water table depth is an observation, not an estimate.
    groundwater_observed: bool = False


@dataclass(frozen=True)
class WaterTableEffect:
    surcharge_kpa: float
    effective_gamma_kn_m3: float
    case: str
    explanation: str


def water_table_effect(
    soil: SoilParameters, footing: Footing, ground: GroundConditions
) -> WaterTableEffect:
    """Surcharge at founding level and the effective unit weight below it.

    Three cases, after Das:

      I   water table at or above founding level
      II  water table within one footing width below the base
      III water table deeper than B below the base — no effect
    """
    d = footing.depth_m
    b = footing.width_m
    gamma = soil.unit_weight_kn_m3
    gamma_sat = soil.gamma_sat
    gamma_sub = gamma_sat - GAMMA_WATER_KN_M3
    dw = ground.groundwater_depth_m

    if dw is None or dw >= d + b:
        return WaterTableEffect(
            surcharge_kpa=gamma * d,
            effective_gamma_kn_m3=gamma,
            case="III",
            explanation=(
                "Water table is deeper than one footing width below the base (or was not "
                "recorded), so no buoyancy reduction is applied."
            ),
        )

    if dw <= d:
        # Case I — submerged from dw down. Surcharge is part moist, part buoyant.
        surcharge = gamma * dw + (gamma_sat - GAMMA_WATER_KN_M3) * (d - dw)
        return WaterTableEffect(
            surcharge_kpa=surcharge,
            effective_gamma_kn_m3=gamma_sub,
            case="I",
            explanation=(
                f"Water table at {dw:.2f} m is at or above founding level ({d:.2f} m). The "
                "soil below the base is buoyant, so the self-weight term uses the submerged "
                f"unit weight ({gamma_sub:.1f} kN/m3) — roughly half the dry value."
            ),
        )

    # Case II — water table between the base and B below it: interpolate.
    effective = gamma_sub + ((dw - d) / b) * (gamma - gamma_sub)
    return WaterTableEffect(
        surcharge_kpa=gamma * d,
        effective_gamma_kn_m3=effective,
        case="II",
        explanation=(
            f"Water table at {dw:.2f} m lies within one footing width below the base, so the "
            f"unit weight in the self-weight term is interpolated to {effective:.1f} kN/m3."
        ),
    )


def _terzaghi_shape_coefficients(footing: Footing) -> tuple[float, float, str]:
    """Terzaghi's cohesion and self-weight coefficients for a footing shape."""
    if footing.shape in ("strip", "square", "circular"):
        sc, sg = TERZAGHI_SHAPE_COEFFICIENTS[footing.shape]
        return float(sc), float(sg), footing.shape
    # Rectangular: interpolate between strip (B/L -> 0) and square (B/L = 1),
    # which is the usual practice where Terzaghi gives only the two endpoints.
    r = min(max(footing.b_over_l, 0.0), 1.0)
    return 1.0 + 0.3 * r, 0.5 - 0.1 * r, "rectangular (interpolated strip-to-square)"


def bearing_capacity(
    *,
    soil: SoilParameters,
    footing: Footing,
    ground: GroundConditions | None = None,
    method: str = "vesic",
    factor_of_safety: float | None = None,
    standard_id: str | None = None,
) -> CalculationRecord:
    """Ultimate and allowable bearing capacity of a shallow foundation."""
    standard: Standard = get_standard(standard_id)
    ground = ground or GroundConditions()
    w = WarningList()
    ledger = ProvenanceLedger()

    inputs: dict[str, Any] = {
        "soil": {
            "unit_weight_kn_m3": soil.unit_weight_kn_m3,
            "saturated_unit_weight_kn_m3": soil.saturated_unit_weight_kn_m3,
            "cohesion_kpa": soil.cohesion_kpa,
            "friction_angle_deg": soil.friction_angle_deg,
            "analysis": soil.analysis,
        },
        "footing": {
            "width_m": footing.width_m,
            "length_m": footing.length_m,
            "depth_m": footing.depth_m,
            "shape": footing.shape,
        },
        "ground": {
            "groundwater_depth_m": ground.groundwater_depth_m,
            "ground_slope_deg": ground.ground_slope_deg,
            "base_tilt_deg": ground.base_tilt_deg,
            "load_inclination_deg": ground.load_inclination_deg,
        },
        "method": method,
        "factor_of_safety": factor_of_safety or standard.default_bearing_fs,
    }

    if footing.shape not in SHAPES:
        raise InvalidInput("shape", f"must be one of {list(SHAPES)} (got {footing.shape!r})")
    require_positive("width_m", footing.width_m)
    require_non_negative("depth_m", footing.depth_m)
    if footing.shape == "rectangular" and footing.length_m is not None:
        require_positive("length_m", footing.length_m)
        if footing.length_m < footing.width_m:
            raise InvalidInput(
                "length_m", "must be the longer plan dimension; swap width and length"
            )
    if ground.groundwater_depth_m is not None:
        require_non_negative("groundwater_depth_m", ground.groundwater_depth_m)
    require_positive("unit_weight_kn_m3", soil.unit_weight_kn_m3)
    if not 10.0 <= soil.unit_weight_kn_m3 <= 24.0:
        w.warn(
            "UNIT_WEIGHT_OUT_OF_RANGE",
            f"Unit weight of {soil.unit_weight_kn_m3} kN/m3 is outside the 10-24 kN/m3 range "
            "of ordinary soils. Check the units — this is not a density in kg/m3.",
            "unit_weight_kn_m3",
        )

    # ---- The refusal path: no strength parameters, no calculation ----
    missing: dict[str, str] = {}
    if soil.analysis == "undrained":
        phi_deg = 0.0
        if soil.cohesion_kpa is None:
            missing["cohesion_kpa"] = (
                "An undrained analysis is bearing capacity from Cu alone. Measure it by "
                "triaxial (UU), field vane or UCS, or run a drained analysis instead."
            )
    else:
        phi_deg = soil.friction_angle_deg if soil.friction_angle_deg is not None else 0.0
        if soil.friction_angle_deg is None and soil.cohesion_kpa is None:
            missing["friction_angle_deg"] = (
                "A drained analysis needs c' or phi'. Obtain them from a direct shear or "
                "triaxial test, or correlate phi' from SPT/CPT and accept the correlation "
                "warning on the result."
            )
    if missing:
        return insufficient_data(
            "bearing_capacity", method, missing, standard=standard, inputs=inputs
        )

    cohesion = soil.cohesion_kpa or 0.0
    require_non_negative("cohesion_kpa", cohesion)
    if soil.analysis == "undrained":
        if soil.friction_angle_deg not in (None, 0.0):
            w.warn(
                "FRICTION_IGNORED_UNDRAINED",
                "An undrained (phi = 0) analysis was requested, so the supplied friction "
                "angle was not used. Run a drained analysis for the long-term case.",
                "friction_angle_deg",
            )
    else:
        require_friction_angle("friction_angle_deg", phi_deg)

    ledger.record(
        "unit_weight_kn_m3",
        Measurement(soil.unit_weight_kn_m3, "kN/m3", soil.unit_weight_source, soil.reference),
    )
    if cohesion or soil.analysis == "undrained":
        ledger.record(
            "cohesion_kpa",
            Measurement(cohesion, "kPa", soil.cohesion_source, soil.reference),
        )
    if soil.analysis != "undrained":
        ledger.record(
            "friction_angle_deg",
            Measurement(phi_deg, "deg", soil.friction_source, soil.reference),
        )

    if soil.saturated_unit_weight_kn_m3 is None and ground.groundwater_depth_m is not None:
        w.warn(
            "ASSUMED_SATURATED_UNIT_WEIGHT",
            "Saturated unit weight was not supplied, so the bulk unit weight was used below "
            "the water table. This is mildly conservative; measure it where the water table "
            "is at or above founding level.",
            "saturated_unit_weight_kn_m3",
        )
    if ground.groundwater_depth_m is not None and not ground.groundwater_observed:
        w.warn(
            "GROUNDWATER_ESTIMATED",
            "The water table depth used here is an estimate, not an observation. Groundwater "
            "at or above founding level roughly halves the self-weight term, so confirm it "
            "in a standpipe over a seasonal cycle.",
            "groundwater_depth_m",
        )

    # ---- Factors ----
    bf: BearingFactors = bearing_factors(phi_deg, method)
    wt = water_table_effect(soil, footing, ground)
    q_surcharge = wt.surcharge_kpa
    gamma_eff = wt.effective_gamma_kn_m3
    d_over_b = footing.depth_m / footing.width_m

    if method == "terzaghi":
        if ground.load_inclination_deg or ground.ground_slope_deg or ground.base_tilt_deg:
            w.warn(
                "TERZAGHI_NO_CORRECTIONS",
                "Terzaghi's method has no inclination, slope or base-tilt factors, so those "
                "inputs were ignored. Choose Hansen or Vesic for an inclined or sloping case.",
                "method",
            )
        sc_coeff, s_gamma_coeff, shape_note = _terzaghi_shape_coefficients(footing)
        term_c = sc_coeff * cohesion * bf.nc
        term_q = q_surcharge * bf.nq
        term_g = s_gamma_coeff * gamma_eff * footing.width_m * bf.n_gamma
        corrections = CorrectionFactors(sc=sc_coeff, s_gamma=s_gamma_coeff * 2.0)
        w.info(
            "TERZAGHI_SHAPE",
            f"Terzaghi shape coefficients for a {shape_note} footing: "
            f"{sc_coeff:.2f} on the cohesion term, {s_gamma_coeff:.2f} on the self-weight term.",
        )
        w.info(
            "TERZAGHI_CONSERVATISM",
            "Terzaghi neglects the shear strength of the soil above founding level and applies "
            "no depth factors, so it under-reads a deeply embedded footing.",
        )
    else:
        if method == "meyerhof":
            corrections = meyerhof_factors(
                phi_deg=phi_deg,
                b_over_l=footing.b_over_l,
                d_over_b=d_over_b,
                load_inclination_deg=ground.load_inclination_deg,
            )
            if ground.ground_slope_deg or ground.base_tilt_deg:
                w.warn(
                    "MEYERHOF_NO_SLOPE_FACTORS",
                    "Meyerhof's method as implemented has no ground-slope or base-tilt "
                    "factors; those inputs were ignored. Use Hansen for a sloping site.",
                    "method",
                )
        else:
            corrections = hansen_vesic_factors(
                phi_deg=phi_deg,
                nq=bf.nq,
                nc=bf.nc,
                b_over_l=footing.b_over_l,
                d_over_b=d_over_b,
                load_inclination_deg=ground.load_inclination_deg,
                ground_slope_deg=ground.ground_slope_deg,
                base_tilt_deg=ground.base_tilt_deg,
                method=method,
            )

        term_c = (
            cohesion * bf.nc * corrections.sc * corrections.dc
            * corrections.ic * corrections.gc * corrections.bc
        )
        term_q = (
            q_surcharge * bf.nq * corrections.sq * corrections.dq
            * corrections.iq * corrections.gq * corrections.bq
        )
        term_g = (
            0.5 * gamma_eff * footing.width_m * bf.n_gamma * corrections.s_gamma
            * corrections.d_gamma * corrections.i_gamma * corrections.g_gamma
            * corrections.b_gamma
        )

    q_ult = term_c + term_q + term_g
    q_net_ult = max(q_ult - q_surcharge, 0.0)

    fs = factor_of_safety if factor_of_safety is not None else standard.default_bearing_fs
    require_positive("factor_of_safety", fs)
    if fs < 2.0:
        w.warn(
            "LOW_FACTOR_OF_SAFETY",
            f"A factor of safety of {fs} is below the 2.5-3.0 normally applied to shallow "
            "foundations under working load. Justify it against the quality of the data.",
            "factor_of_safety",
        )

    q_allow_net = q_net_ult / fs
    q_allow_gross = q_allow_net + q_surcharge

    if footing.depth_m < 0.5:
        w.warn(
            "SHALLOW_FOUNDING_DEPTH",
            f"A founding depth of {footing.depth_m:.2f} m is within the zone of seasonal "
            "moisture change, frost and topsoil in most climates. Found below it.",
            "depth_m",
        )
    if d_over_b > 3.0:
        w.warn(
            "DEEP_FOUNDATION_RANGE",
            f"D/B = {d_over_b:.1f} is beyond the range shallow-foundation theory is derived "
            "for. Assess this as a pier or pile rather than a footing.",
            "depth_m",
        )

    if ledger.unmeasured():
        w.warn(
            "PRELIMINARY_RESULT",
            "This bearing capacity was computed from at least one parameter that was "
            "correlated or assumed rather than measured ("
            + ", ".join(sorted(ledger.unmeasured()))
            + "). It is a preliminary screening value and requires engineer review.",
        )

    results = {
        "ultimate_capacity_kpa": round(q_ult, 1),
        "net_ultimate_capacity_kpa": round(q_net_ult, 1),
        "gross_allowable_capacity_kpa": round(q_allow_gross, 1),
        "net_allowable_capacity_kpa": round(q_allow_net, 1),
        "factor_of_safety": fs,
        "surcharge_kpa": round(q_surcharge, 1),
        "effective_unit_weight_kn_m3": round(gamma_eff, 2),
        "terms_kpa": {
            "cohesion": round(term_c, 1),
            "surcharge": round(term_q, 1),
            "self_weight": round(term_g, 1),
        },
        "bearing_factors": bf.as_dict(),
        "correction_factors": corrections.as_dict(),
        "water_table": {
            "case": wt.case,
            "explanation": wt.explanation,
        },
        "analysis": soil.analysis,
    }

    return CalculationRecord(
        calculation_type="bearing_capacity",
        method=method,
        status=Status.CALCULATED,
        inputs=inputs,
        results=results,
        warnings=w,
        provenance=ledger,
        standard_id=standard.id,
        standard_edition=standard.edition,
    )
