"""Empirical correlations — the honest part of geotechnics.

Every function here converts a field measurement into a design parameter
using a published empirical relationship. They are all scattered, some
badly: a friction angle from SPT blow counts carries perhaps +/- 3 degrees,
and an undrained strength from N carries a factor of two.

So each correlation returns a ``Correlated`` result that names the method,
cites it, and marks the value ``Source.ESTIMATED``. The bearing-capacity
engine will happily use it and the report will state, in the provenance
table, that it was correlated rather than measured. Spec rule 6: nothing is
silently substituted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..provenance import Measurement, Source
from ..units import GAMMA_WATER_KN_M3
from ..warnings import InvalidInput, WarningList, require_non_negative, require_positive


@dataclass(frozen=True)
class Correlated:
    measurement: Measurement
    method: str
    citation: str
    warnings: WarningList

    @property
    def value(self) -> float:
        return self.measurement.value


# ───────────────────────── SPT corrections ─────────────────────────

#: Rod-length correction to SPT energy, after Skempton (1986) / ASTM D6066.
def rod_length_factor(rod_length_m: float) -> float:
    if rod_length_m > 10:
        return 1.0
    if rod_length_m > 6:
        return 0.95
    if rod_length_m > 4:
        return 0.85
    return 0.75


def borehole_diameter_factor(diameter_mm: float) -> float:
    """Skempton (1986): larger holes relax the ground and lower N."""
    if diameter_mm <= 115:
        return 1.0
    if diameter_mm <= 150:
        return 1.05
    return 1.15


@dataclass(frozen=True)
class SptCorrection:
    n_raw: int
    n60: float
    n1_60: float | None
    energy_ratio: float
    ce: float
    cb: float
    cr: float
    cs: float
    cn: float | None
    method: str
    warnings: WarningList

    def as_dict(self) -> dict[str, float | int | str | None]:
        return {
            "n_raw": self.n_raw,
            "n60": round(self.n60, 1),
            "n1_60": None if self.n1_60 is None else round(self.n1_60, 1),
            "energy_ratio": self.energy_ratio,
            "ce": round(self.ce, 3),
            "cb": self.cb,
            "cr": self.cr,
            "cs": self.cs,
            "cn": None if self.cn is None else round(self.cn, 3),
            "method": self.method,
        }


def correct_spt(
    *,
    n_raw: int,
    energy_ratio_percent: float = 60.0,
    borehole_diameter_mm: float = 100.0,
    rod_length_m: float = 6.0,
    liner_absent_in_lined_sampler: bool = False,
    effective_overburden_kpa: float | None = None,
) -> SptCorrection:
    """Correct a raw SPT blow count to N60, and to (N1)60 where overburden is known.

    Spec section 15: corrections are never applied silently. Every factor is
    returned separately so the report can show the arithmetic:

        N60  = N_raw x CE x CB x CR x CS
        (N1)60 = N60 x CN,  CN = sqrt(100 / sigma'_v)   (Liao & Whitman 1986)

    ``CN`` is capped at 1.7, because at shallow depth the uncorrected form
    runs away and would flatter a loose soil into a dense one.
    """
    w = WarningList()
    if n_raw < 0:
        raise InvalidInput("n_raw", f"cannot be negative (got {n_raw})")
    if energy_ratio_percent <= 0 or energy_ratio_percent > 100:
        raise InvalidInput(
            "energy_ratio_percent", f"must be between 0 and 100 (got {energy_ratio_percent})"
        )

    ce = energy_ratio_percent / 60.0
    cb = borehole_diameter_factor(require_positive("borehole_diameter_mm", borehole_diameter_mm))
    cr = rod_length_factor(require_positive("rod_length_m", rod_length_m))
    cs = 1.2 if liner_absent_in_lined_sampler else 1.0

    if energy_ratio_percent == 60.0:
        w.info(
            "ASSUMED_ENERGY_RATIO",
            "Hammer energy ratio was not measured; 60% was used, which is the reference "
            "value the correlations are defined at. A donut hammer commonly delivers 45%.",
            "energy_ratio_percent",
        )

    n60 = n_raw * ce * cb * cr * cs

    cn: float | None = None
    n1_60: float | None = None
    if effective_overburden_kpa is not None:
        sigma = require_positive("effective_overburden_kpa", effective_overburden_kpa)
        cn = min(math.sqrt(100.0 / sigma), 1.7)
        n1_60 = n60 * cn
        if sigma < 25:
            w.warn(
                "SHALLOW_OVERBURDEN_CORRECTION",
                f"Effective overburden of {sigma:.0f} kPa is very low, so the overburden "
                "correction is at or near its 1.7 cap and (N1)60 is unreliable here.",
                "effective_overburden_kpa",
            )
    else:
        w.warn(
            "NO_OVERBURDEN_CORRECTION",
            "Effective overburden pressure was not supplied, so (N1)60 was not computed. "
            "Correlations that need a normalised blow count cannot be run.",
            "effective_overburden_kpa",
        )

    if n_raw > 50:
        w.info(
            "REFUSAL",
            f"N = {n_raw} indicates refusal or very dense/cemented ground. Confirm the "
            "penetration recorded for the final increment.",
            "n_raw",
        )
    return SptCorrection(
        n_raw=n_raw,
        n60=n60,
        n1_60=n1_60,
        energy_ratio=energy_ratio_percent,
        ce=ce,
        cb=cb,
        cr=cr,
        cs=cs,
        cn=cn,
        method="skempton_1986",
        warnings=w,
    )


def friction_angle_from_spt(n1_60: float, *, reference: str | None = None) -> Correlated:
    """Friction angle of a granular soil from (N1)60.

    Peck, Hanson & Thornburn (1974), in the algebraic form given by Wolff
    (1989):  phi = 27.1 + 0.3 (N1)60 - 0.00054 (N1)60^2

    Scatter is roughly +/- 3 degrees. For anything where the friction angle
    governs, this is a screening value, not a design value.
    """
    w = WarningList()
    n = require_non_negative("n1_60", n1_60)
    phi = 27.1 + 0.3 * n - 0.00054 * n * n
    phi = max(min(phi, 45.0), 25.0)
    w.warn(
        "CORRELATED_FRICTION_ANGLE",
        f"Friction angle of {phi:.1f} deg was correlated from (N1)60 = {n:.0f}, not measured. "
        "The correlation scatters by about +/- 3 degrees; confirm by triaxial or direct shear "
        "test where the friction angle governs the design.",
        "friction_angle_deg",
    )
    return Correlated(
        Measurement(round(phi, 1), "deg", Source.ESTIMATED, reference, note="from SPT (N1)60"),
        "peck_hanson_thornburn_1974",
        "Peck, Hanson & Thornburn (1974); algebraic form after Wolff (1989)",
        w,
    )


def relative_density_from_spt(n1_60: float, *, reference: str | None = None) -> Correlated:
    """Relative density of a sand from (N1)60, after Skempton (1986): Dr = sqrt(N/60)."""
    w = WarningList()
    n = require_non_negative("n1_60", n1_60)
    dr = min(math.sqrt(n / 60.0), 1.0)
    w.info(
        "CORRELATED_RELATIVE_DENSITY",
        f"Relative density {dr * 100:.0f}% correlated from (N1)60 = {n:.0f}.",
        "relative_density",
    )
    return Correlated(
        Measurement(round(dr, 3), "-", Source.ESTIMATED, reference, note="from SPT (N1)60"),
        "skempton_1986",
        "Skempton, A.W. (1986) Geotechnique 36(3), 425-447",
        w,
    )


def undrained_strength_from_spt(
    n60: float, *, factor: float = 4.5, reference: str | None = None
) -> Correlated:
    """Undrained shear strength of a clay from N60: Cu = k x N60 kPa.

    Stroud (1974) gives k between 4 and 6 kPa per blow depending on plasticity;
    4.5 is the middle of the band for a clay of ordinary plasticity. The
    scatter on this is close to a factor of two, which is why a CRITICAL-
    adjacent warning rides with it and why any raft or settlement-governed
    design should use a measured Cu instead.
    """
    w = WarningList()
    n = require_non_negative("n60", n60)
    if not 3.0 <= factor <= 7.0:
        raise InvalidInput("factor", f"must lie between 3 and 7 kPa/blow (got {factor})")
    cu = factor * n
    w.warn(
        "CORRELATED_UNDRAINED_STRENGTH",
        f"Cu = {cu:.0f} kPa was correlated from N60 = {n:.0f} using {factor} kPa per blow. "
        "This correlation scatters by roughly a factor of two. Use a measured Cu (triaxial, "
        "vane or UCS) before relying on it for design.",
        "cohesion_kpa",
    )
    return Correlated(
        Measurement(round(cu, 1), "kPa", Source.ESTIMATED, reference, note="from SPT N60"),
        "stroud_1974",
        "Stroud, M.A. (1974) Proc. European Symposium on Penetration Testing",
        w,
    )


def youngs_modulus_from_spt(
    n60: float, *, soil_family: str = "sand", reference: str | None = None
) -> Correlated:
    """Drained Young's modulus for settlement screening, after Bowles (1996).

    sand:        Es = 500 (N60 + 15) kPa
    silty sand:  Es = 300 (N60 + 6)  kPa
    clayey sand: Es = 320 (N60 + 15) kPa
    gravelly:    Es = 1200 (N60 + 6) kPa
    """
    w = WarningList()
    n = require_non_negative("n60", n60)
    table = {
        "sand": (500.0, 15.0),
        "silty_sand": (300.0, 6.0),
        "clayey_sand": (320.0, 15.0),
        "gravel": (1200.0, 6.0),
    }
    if soil_family not in table:
        raise InvalidInput("soil_family", f"must be one of {sorted(table)} (got {soil_family!r})")
    a, b = table[soil_family]
    es = a * (n + b)
    w.warn(
        "CORRELATED_MODULUS",
        f"Es = {es / 1000:.0f} MPa was correlated from N60 = {n:.0f} for {soil_family}. "
        "Settlement is directly proportional to 1/Es, so a correlated modulus makes the "
        "settlement estimate an order-of-magnitude screen.",
        "youngs_modulus_kpa",
    )
    return Correlated(
        Measurement(round(es, 0), "kPa", Source.ESTIMATED, reference, note="from SPT N60"),
        "bowles_1996",
        "Bowles, J.E. (1996) Foundation Analysis and Design, 5th ed., Table 5-6",
        w,
    )


# ───────────────────────────── DCP ─────────────────────────────

def dcp_index(*, blows: int, penetration_mm: float) -> float:
    """DCP penetration index, mm per blow."""
    b = require_positive("blows", blows)
    p = require_positive("penetration_mm", penetration_mm)
    return p / b


def cbr_from_dcp(dcp_index_mm_per_blow: float, *, reference: str | None = None) -> Correlated:
    """CBR from the DCP index, using the TRL / Kleyn relationship.

        log10(CBR) = 2.632 - 1.28 log10(DN)

    This is the correlation the road sector runs on — subgrade acceptance on
    most Kenyan and southern African road contracts is a DCP result read
    through it.
    """
    w = WarningList()
    dn = require_positive("dcp_index_mm_per_blow", dcp_index_mm_per_blow)
    cbr = 10 ** (2.632 - 1.28 * math.log10(dn))
    if dn > 60:
        w.warn(
            "VERY_SOFT_SUBGRADE",
            f"DN = {dn:.0f} mm/blow indicates a very weak subgrade (CBR about {cbr:.1f}%). "
            "Expect to improve, stabilise or replace this material.",
            "dcp_index",
        )
    w.info(
        "EMPIRICAL_CORRELATION",
        "CBR from DCP is an empirical correlation (TRL / Kleyn), not a CBR test. "
        "Report it as a DCP-derived CBR, and confirm by laboratory CBR where the "
        "pavement design depends on it.",
    )
    return Correlated(
        Measurement(round(cbr, 1), "%", Source.ESTIMATED, reference, note="from DCP index"),
        "trl_kleyn",
        "Kleyn (1975); TRL Overseas Road Note 31 / ORN 18",
        w,
    )


def subgrade_class_from_cbr(cbr_percent: float) -> str:
    """Road subgrade class from CBR, after TRL ORN 31 (S1 weakest, S6 best)."""
    c = require_positive("cbr_percent", cbr_percent)
    if c < 3:
        return "S1"
    if c < 5:
        return "S2"
    if c < 8:
        return "S3"
    if c < 15:
        return "S4"
    if c < 30:
        return "S5"
    return "S6"


# ───────────────────────────── CPT ─────────────────────────────

@dataclass(frozen=True)
class CptPoint:
    depth_m: float
    qc_mpa: float
    fs_kpa: float
    u2_kpa: float | None = None


def friction_ratio(qc_mpa: float, fs_kpa: float) -> float:
    """Rf = fs / qc as a percentage, with both terms in the same unit."""
    q = require_positive("qc_mpa", qc_mpa)
    f = require_non_negative("fs_kpa", fs_kpa)
    return (f / (q * 1000.0)) * 100.0


def soil_behaviour_type(qc_mpa: float, fs_kpa: float) -> str:
    """Coarse soil behaviour type from the friction ratio.

    A deliberately simple reading of the Robertson chart: it tells sand from
    clay well, and it is labelled a *behaviour* type because a CPT measures
    how the ground behaves, not what it is made of.
    """
    rf = friction_ratio(qc_mpa, fs_kpa)
    if rf < 1.0:
        return "Sand to gravelly sand"
    if rf < 2.0:
        return "Sand, locally silty"
    if rf < 3.5:
        return "Silty sand to sandy silt"
    if rf < 5.0:
        return "Clayey silt to silty clay"
    if rf < 8.0:
        return "Clay"
    return "Organic soil or peat"


def undrained_strength_from_cpt(
    *,
    qc_mpa: float,
    total_overburden_kpa: float,
    nk: float = 17.0,
    reference: str | None = None,
) -> Correlated:
    """Cu = (qc - sigma_v0) / Nk, after Lunne, Robertson & Powell (1997).

    Nk is typically 15-20 for ordinary clays and is the main source of
    uncertainty, so it is an explicit input rather than a buried constant.
    """
    w = WarningList()
    qc = require_positive("qc_mpa", qc_mpa) * 1000.0
    sv = require_non_negative("total_overburden_kpa", total_overburden_kpa)
    if not 10.0 <= nk <= 25.0:
        raise InvalidInput("nk", f"cone factor must lie between 10 and 25 (got {nk})")
    cu = (qc - sv) / nk
    if cu <= 0:
        w.critical(
            "NEGATIVE_UNDRAINED_STRENGTH",
            "Cone resistance is below the total overburden pressure, which gives a negative "
            "Cu. Check the depth, the units of qc and the overburden calculation.",
            "cohesion_kpa",
        )
    w.warn(
        "CORRELATED_UNDRAINED_STRENGTH",
        f"Cu = {cu:.0f} kPa correlated from CPT with Nk = {nk:.0f}. Nk between 15 and 20 "
        "changes this result by about 25%.",
        "cohesion_kpa",
    )
    return Correlated(
        Measurement(round(cu, 1), "kPa", Source.ESTIMATED, reference, note="from CPT qc"),
        "lunne_robertson_powell_1997",
        "Lunne, Robertson & Powell (1997) Cone Penetration Testing in Geotechnical Practice",
        w,
    )


def friction_angle_from_cpt(
    *, qc_mpa: float, effective_overburden_kpa: float, reference: str | None = None
) -> Correlated:
    """Friction angle of a sand from CPT, after Robertson & Campanella (1983).

        tan(phi) = (1 / 2.68) [ log10(qc / sigma'_v0) + 0.29 ]
    """
    w = WarningList()
    qc = require_positive("qc_mpa", qc_mpa) * 1000.0
    sv = require_positive("effective_overburden_kpa", effective_overburden_kpa)
    phi = math.degrees(math.atan((1.0 / 2.68) * (math.log10(qc / sv) + 0.29)))
    phi = max(min(phi, 45.0), 25.0)
    w.warn(
        "CORRELATED_FRICTION_ANGLE",
        f"Friction angle {phi:.1f} deg correlated from CPT. Applies to clean, uncemented "
        "quartz sand; it over-reads in cemented or calcareous sand.",
        "friction_angle_deg",
    )
    return Correlated(
        Measurement(round(phi, 1), "deg", Source.ESTIMATED, reference, note="from CPT qc"),
        "robertson_campanella_1983",
        "Robertson, P.K. & Campanella, R.G. (1983) Canadian Geotechnical Journal 20(4)",
        w,
    )


def effective_overburden(
    *, depth_m: float, unit_weight_kn_m3: float, groundwater_depth_m: float | None
) -> float:
    """Vertical effective stress at a depth, given one unit weight and a water table."""
    z = require_non_negative("depth_m", depth_m)
    gamma = require_positive("unit_weight_kn_m3", unit_weight_kn_m3)
    if groundwater_depth_m is None or groundwater_depth_m >= z:
        return gamma * z
    dw = require_non_negative("groundwater_depth_m", groundwater_depth_m)
    return gamma * dw + (gamma - GAMMA_WATER_KN_M3) * (z - dw)
