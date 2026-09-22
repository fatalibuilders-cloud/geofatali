"""Unified Soil Classification System, to ASTM D2487.

This is a deterministic classification from index-test results. It is the
LAB_CONFIRMED path in the spec's section 12, and it is deliberately separate
from anything the vision model produces: a class returned from here is
defensible from the grading curve and the Atterberg limits, and one returned
from a photograph is an opinion about a picture.

Inputs are the numbers that come off a standard grading and limits sheet:

    fines_percent      passing the 0.075 mm (No. 200) sieve
    gravel_percent     retained on the 4.75 mm (No. 4) sieve
    sand_percent       passing 4.75 mm, retained on 0.075 mm
    liquid_limit       LL, per cent
    plastic_limit      PL, per cent
    cu, cc             coefficients of uniformity and curvature
"""

from __future__ import annotations

from dataclasses import dataclass

from ..warnings import InvalidInput, WarningList

#: The Casagrande A-line: PI = 0.73 (LL - 20).
def a_line_pi(liquid_limit: float) -> float:
    return 0.73 * (liquid_limit - 20.0)


#: The U-line, the empirical upper bound of real soils: PI = 0.9 (LL - 8).
def u_line_pi(liquid_limit: float) -> float:
    return 0.9 * (liquid_limit - 8.0)


#: Plain-language names for every symbol the classifier can return.
USCS_NAMES: dict[str, str] = {
    "GW": "Well-graded gravel",
    "GP": "Poorly graded gravel",
    "GM": "Silty gravel",
    "GC": "Clayey gravel",
    "GC-GM": "Silty, clayey gravel",
    "GW-GM": "Well-graded gravel with silt",
    "GW-GC": "Well-graded gravel with clay",
    "GP-GM": "Poorly graded gravel with silt",
    "GP-GC": "Poorly graded gravel with clay",
    "SW": "Well-graded sand",
    "SP": "Poorly graded sand",
    "SM": "Silty sand",
    "SC": "Clayey sand",
    "SC-SM": "Silty, clayey sand",
    "SW-SM": "Well-graded sand with silt",
    "SW-SC": "Well-graded sand with clay",
    "SP-SM": "Poorly graded sand with silt",
    "SP-SC": "Poorly graded sand with clay",
    "ML": "Silt (low plasticity)",
    "CL": "Lean clay",
    "CL-ML": "Silty clay",
    "MH": "Elastic silt",
    "CH": "Fat clay",
    "OL": "Organic silt or organic clay (low plasticity)",
    "OH": "Organic clay or organic silt (high plasticity)",
    "PT": "Peat",
}

#: Symbols that mean trouble: highly compressible, organic or expansive.
PROBLEM_SYMBOLS = frozenset({"CH", "MH", "OH", "OL", "PT"})

#: Symbols with material shrink-swell potential — the black cotton family.
EXPANSIVE_SYMBOLS = frozenset({"CH", "CL"})


@dataclass(frozen=True)
class IndexTests:
    """What a standard index-test sheet reports."""

    fines_percent: float | None = None
    gravel_percent: float | None = None
    sand_percent: float | None = None
    liquid_limit: float | None = None
    plastic_limit: float | None = None
    cu: float | None = None
    cc: float | None = None
    organic: bool = False
    peat: bool = False

    @property
    def plasticity_index(self) -> float | None:
        if self.liquid_limit is None or self.plastic_limit is None:
            return None
        return self.liquid_limit - self.plastic_limit


@dataclass(frozen=True)
class Classification:
    symbol: str
    name: str
    group_name: str
    plasticity_index: float | None
    warnings: WarningList
    #: "LAB_CONFIRMED_CLASSIFICATION" here; the AI path uses its own marker.
    basis: str = "LAB_CONFIRMED_CLASSIFICATION"


def _fine_symbol(ll: float, pi: float, organic: bool) -> str:
    """Plasticity-chart branch for a soil with 50% or more fines."""
    above_a = pi > a_line_pi(ll)
    if organic:
        return "OL" if ll < 50 else "OH"
    if ll < 50:
        if pi < 4 or not above_a:
            return "ML"
        if pi > 7 and above_a:
            return "CL"
        return "CL-ML"  # 4 <= PI <= 7 and on or above the A-line
    return "CH" if above_a else "MH"


def _gradation_symbol(prefix: str, cu: float | None, cc: float | None, w: WarningList) -> str:
    """W (well graded) or P (poorly graded) for a clean coarse soil."""
    if cu is None or cc is None:
        w.warn(
            "MISSING_GRADATION_COEFFICIENTS",
            "Cu and Cc were not supplied, so the soil cannot be told well-graded from "
            "poorly graded. Reported as poorly graded, which is the conservative choice.",
            "cu/cc",
        )
        return f"{prefix}P"
    cu_limit = 4.0 if prefix == "G" else 6.0
    well_graded = cu >= cu_limit and 1.0 <= cc <= 3.0
    return f"{prefix}{'W' if well_graded else 'P'}"


def classify_uscs(tests: IndexTests) -> Classification:
    """Classify a soil from its index tests.

    Raises ``InvalidInput`` for impossible data (negative percentages, a
    plastic limit above the liquid limit). Missing but non-fatal data produces
    warnings and the conservative branch, never a silent guess.
    """
    w = WarningList()

    if tests.peat:
        return Classification("PT", USCS_NAMES["PT"], "Peat", None, w)

    if tests.fines_percent is None:
        raise InvalidInput(
            "fines_percent",
            "is required to classify a soil — it is the percentage passing the 0.075 mm sieve",
        )
    for name, value in (
        ("fines_percent", tests.fines_percent),
        ("gravel_percent", tests.gravel_percent),
        ("sand_percent", tests.sand_percent),
    ):
        if value is not None and not 0 <= value <= 100:
            raise InvalidInput(name, f"must be between 0 and 100 (got {value})")

    pi = tests.plasticity_index
    ll = tests.liquid_limit
    if pi is not None and pi < 0:
        raise InvalidInput(
            "plastic_limit", "cannot exceed the liquid limit — check the limits sheet"
        )
    if ll is not None and pi is not None and pi > u_line_pi(ll) and ll > 8:
        w.warn(
            "ABOVE_U_LINE",
            f"PI = {pi:.0f} at LL = {ll:.0f} plots above the U-line, which no natural soil "
            "does. Re-check the Atterberg limits before using this classification.",
            "plasticity",
        )

    # ---- Fine-grained: 50% or more passes the 0.075 mm sieve ----
    if tests.fines_percent >= 50:
        if ll is None or pi is None:
            raise InvalidInput(
                "liquid_limit/plastic_limit",
                "are required for a fine-grained soil — the plasticity chart needs both",
            )
        symbol = _fine_symbol(ll, pi, tests.organic)
        if tests.organic:
            w.info(
                "ORGANIC_FLAGGED",
                "Classified as organic on the supplied flag. ASTM D2487 confirms this with "
                "the oven-dried to not-dried liquid-limit ratio (< 0.75).",
            )
        group = "Fine-grained soil (50% or more fines)"
        return Classification(symbol, USCS_NAMES[symbol], group, pi, w)

    # ---- Coarse-grained ----
    gravel = tests.gravel_percent
    sand = tests.sand_percent
    if gravel is None and sand is None:
        raise InvalidInput(
            "gravel_percent/sand_percent",
            "at least one is required to tell a gravel from a sand",
        )
    coarse_total = 100.0 - tests.fines_percent
    if gravel is None:
        gravel = max(coarse_total - (sand or 0.0), 0.0)
    if sand is None:
        sand = max(coarse_total - gravel, 0.0)
    prefix = "G" if gravel > sand else "S"
    group = "Coarse-grained soil — gravel" if prefix == "G" else "Coarse-grained soil — sand"

    if tests.fines_percent < 5:
        symbol = _gradation_symbol(prefix, tests.cu, tests.cc, w)
        return Classification(symbol, USCS_NAMES[symbol], group, pi, w)

    if tests.fines_percent > 12:
        if ll is None or pi is None:
            raise InvalidInput(
                "liquid_limit/plastic_limit",
                f"are required: the soil has {tests.fines_percent:.0f}% fines, and the "
                "plasticity of those fines decides between the M (silty) and C (clayey) symbols",
            )
        fine = _fine_symbol(ll, pi, organic=False)
        if fine == "CL-ML":
            symbol = f"{prefix}C-{prefix}M"
        elif fine in ("ML", "MH"):
            symbol = f"{prefix}M"
        else:
            symbol = f"{prefix}C"
        return Classification(symbol, USCS_NAMES[symbol], group, pi, w)

    # 5-12% fines: borderline, ASTM requires a dual symbol.
    gradation = _gradation_symbol(prefix, tests.cu, tests.cc, w)
    if ll is None or pi is None:
        raise InvalidInput(
            "liquid_limit/plastic_limit",
            f"are required: {tests.fines_percent:.0f}% fines is the borderline band and "
            "ASTM D2487 needs a dual symbol, which depends on the plasticity of the fines",
        )
    fine = _fine_symbol(ll, pi, organic=False)
    second = "M" if fine in ("ML", "MH", "CL-ML") else "C"
    symbol = f"{gradation}-{prefix}{second}"
    w.info(
        "DUAL_SYMBOL",
        f"{tests.fines_percent:.0f}% fines falls in the 5-12% borderline band, so ASTM D2487 "
        "requires the dual symbol reported here.",
    )
    return Classification(symbol, USCS_NAMES.get(symbol, symbol), group, pi, w)


def is_problem_soil(symbol: str) -> bool:
    """Soils that need a settlement or swell check before anything is founded on them."""
    return symbol.split("-")[0] in PROBLEM_SYMBOLS


def swell_potential(pi: float | None) -> str:
    """Shrink-swell potential from plasticity index.

    Bands after Holtz & Gibbs / IS 1498 practice. This is the check that
    catches black cotton soil before someone pours a strip footing on it.
    """
    if pi is None:
        return "UNKNOWN"
    if pi < 12:
        return "LOW"
    if pi < 23:
        return "MEDIUM"
    if pi < 32:
        return "HIGH"
    return "VERY_HIGH"
