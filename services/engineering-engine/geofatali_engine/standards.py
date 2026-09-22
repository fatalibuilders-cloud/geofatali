"""Design standards and calculation methods, as data rather than code.

Spec section 47: standards change, so they are not hard-coded into the
calculation bodies. A calculation is told which standard configuration it is
running under, and it records that choice in its result alongside the method
name and the engine version.

The engine does not claim to *implement* these standards in full. It
implements named, published calculation methods and records which standard
the user is working to, so that the factor of safety, the load combination
and the terminology in the report all match one another.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LoadCombination:
    name: str
    #: Partial factor on permanent actions (Gk).
    gamma_g: float
    #: Partial factor on variable actions (Qk).
    gamma_q: float
    note: str = ""


@dataclass(frozen=True)
class Standard:
    id: str
    name: str
    edition: str
    jurisdiction: str
    #: Typical factor of safety on net ultimate bearing capacity for shallow
    #: foundations under a working (service) load check.
    default_bearing_fs: float
    combinations: tuple[LoadCombination, ...]
    #: Which combination is the service (working) case, and which is the
    #: ultimate case for structural sizing. Named explicitly rather than
    #: taken positionally: Eurocode's Design Approach 1 Combination 2 is last
    #: in the tuple but is NOT the load set a footing is sized on.
    service_combination_name: str
    ultimate_combination_name: str
    #: Permissible total settlement for ordinary framed buildings, mm.
    settlement_limit_mm: float
    #: Permissible angular distortion (delta/L) before architectural damage.
    angular_distortion_limit: float
    reference: str

    def combination(self, name: str) -> LoadCombination:
        for c in self.combinations:
            if c.name == name:
                return c
        raise KeyError(f"{self.id} has no load combination named {name!r}")

    @property
    def service_combination(self) -> LoadCombination:
        return self.combination(self.service_combination_name)

    @property
    def ultimate_combination(self) -> LoadCombination:
        return self.combination(self.ultimate_combination_name)


EUROCODE = Standard(
    id="eurocode",
    name="Eurocode 7 / EN 1997 with EN 1990 actions",
    edition="EN 1997-1:2004 + A1:2013",
    jurisdiction="EU and adopting states (incl. Kenya in practice)",
    default_bearing_fs=3.0,
    combinations=(
        LoadCombination("characteristic", 1.0, 1.0, "Service/characteristic combination"),
        LoadCombination("sls_quasi_permanent", 1.0, 0.3, "Quasi-permanent, for settlement"),
        LoadCombination("uls_set_b", 1.35, 1.5, "EN 1990 eq. 6.10, Design Approach 1 Combination 1"),
        LoadCombination("uls_set_c", 1.0, 1.3, "Design Approach 1 Combination 2, material factors applied"),
    ),
    service_combination_name="characteristic",
    ultimate_combination_name="uls_set_b",
    settlement_limit_mm=50.0,
    angular_distortion_limit=1 / 500,
    reference="EN 1997-1 Annex D; EN 1990 Table A1.2",
)

BRITISH_STANDARD = Standard(
    id="bs",
    name="British Standards (BS 8004 foundations, BS 8110 concrete)",
    edition="BS 8004:2015 / BS 8110-1:1997",
    jurisdiction="UK and legacy Commonwealth practice",
    default_bearing_fs=3.0,
    combinations=(
        LoadCombination("working", 1.0, 1.0, "Working (permissible) load"),
        LoadCombination("uls", 1.4, 1.6, "BS 8110 ultimate load combination"),
    ),
    service_combination_name="working",
    ultimate_combination_name="uls",
    settlement_limit_mm=50.0,
    angular_distortion_limit=1 / 500,
    reference="BS 8004:2015; BS 8110-1:1997 cl. 2.4.3",
)

KENYA = Standard(
    id="kebs",
    name="Kenya — National Building Code 2024 with Eurocode/BS practice",
    edition="NBC 2024; KS adoptions of EN 1997",
    jurisdiction="Kenya",
    default_bearing_fs=3.0,
    combinations=(
        LoadCombination("characteristic", 1.0, 1.0, "Service combination"),
        LoadCombination("uls_set_b", 1.35, 1.5, "As EN 1990 eq. 6.10"),
    ),
    service_combination_name="characteristic",
    ultimate_combination_name="uls_set_b",
    settlement_limit_mm=50.0,
    angular_distortion_limit=1 / 500,
    reference="Kenya National Building Code 2024; KEBS KS EN 1997-1",
)

INDIAN_STANDARD = Standard(
    id="is",
    name="Indian Standards (IS 6403 bearing capacity, IS 456 concrete)",
    edition="IS 6403:1981 (R2002) / IS 456:2000",
    jurisdiction="India",
    default_bearing_fs=2.5,
    combinations=(
        LoadCombination("working", 1.0, 1.0, "Working stress"),
        LoadCombination("uls", 1.5, 1.5, "IS 456 limit state"),
    ),
    service_combination_name="working",
    ultimate_combination_name="uls",
    settlement_limit_mm=50.0,
    angular_distortion_limit=1 / 500,
    reference="IS 6403:1981; IS 1904:1986 settlement limits",
)

AASHTO_LRFD = Standard(
    id="aashto",
    name="AASHTO LRFD Bridge Design Specifications",
    edition="9th edition",
    jurisdiction="United States (transportation structures)",
    default_bearing_fs=3.0,
    combinations=(
        LoadCombination("service_i", 1.0, 1.0, "Service I — settlement and bearing checks"),
        LoadCombination("strength_i", 1.25, 1.75, "Strength I — dead and live load"),
    ),
    service_combination_name="service_i",
    ultimate_combination_name="strength_i",
    settlement_limit_mm=25.0,
    angular_distortion_limit=1 / 250,
    reference="AASHTO LRFD 9th ed. section 10",
)

STANDARDS: dict[str, Standard] = {
    s.id: s for s in (EUROCODE, BRITISH_STANDARD, KENYA, INDIAN_STANDARD, AASHTO_LRFD)
}

DEFAULT_STANDARD_ID = "eurocode"


def get_standard(standard_id: str | None) -> Standard:
    if standard_id is None:
        return STANDARDS[DEFAULT_STANDARD_ID]
    try:
        return STANDARDS[standard_id]
    except KeyError as exc:  # pragma: no cover - guarded at the API edge
        raise KeyError(
            f"Unknown design standard {standard_id!r}. Known: {sorted(STANDARDS)}"
        ) from exc


@dataclass(frozen=True)
class MethodReference:
    """The published source behind one calculation method."""

    method: str
    title: str
    citation: str
    note: str = ""


#: Every method the engine can run, with the reference a reviewer would check.
METHOD_REFERENCES: dict[str, MethodReference] = {
    "terzaghi": MethodReference(
        "terzaghi",
        "Terzaghi general bearing capacity",
        "Terzaghi, K. (1943) Theoretical Soil Mechanics, Wiley, ch. 8",
        "Neglects shear strength of the soil above founding level; no depth factors.",
    ),
    "meyerhof": MethodReference(
        "meyerhof",
        "Meyerhof bearing capacity with shape, depth and inclination factors",
        "Meyerhof, G.G. (1963) Canadian Geotechnical Journal 1(1), 16-26",
    ),
    "hansen": MethodReference(
        "hansen",
        "Brinch Hansen general bearing capacity",
        "Hansen, J.B. (1970) Danish Geotechnical Institute Bulletin No. 28",
        "Supports ground slope and base tilt.",
    ),
    "vesic": MethodReference(
        "vesic",
        "Vesic bearing capacity",
        "Vesic, A.S. (1973) ASCE JSMFD 99(SM1), 45-73",
        "N-gamma is larger than Hansen's; the usual choice for granular soils.",
    ),
    "elastic_settlement": MethodReference(
        "elastic_settlement",
        "Elastic (immediate) settlement of a loaded area",
        "Bowles, J.E. (1996) Foundation Analysis and Design, 5th ed., ch. 5",
    ),
    "consolidation_1d": MethodReference(
        "consolidation_1d",
        "One-dimensional primary consolidation settlement",
        "Terzaghi & Peck (1967); Das, Principles of Geotechnical Engineering, ch. 11",
    ),
    "secondary_compression": MethodReference(
        "secondary_compression",
        "Secondary compression (creep) settlement",
        "Mesri & Godlewski (1977) ASCE JGED 103(GT5)",
    ),
    "stress_2to1": MethodReference(
        "stress_2to1",
        "2:1 approximate stress distribution under a footing",
        "Das, Principles of Foundation Engineering, ch. 6",
    ),
    "boussinesq_rectangle": MethodReference(
        "boussinesq_rectangle",
        "Boussinesq vertical stress under the corner of a loaded rectangle",
        "Boussinesq (1885); Newmark (1935) influence factors",
    ),
}
