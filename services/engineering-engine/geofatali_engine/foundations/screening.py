"""Foundation option screening.

Spec sections 28-30, and the rule that matters most: *do not output a single
automatic "approved foundation"*. This engine outputs CANDIDATE options, each
one with the criteria it passed, the criteria a human has to look at, and the
data that is missing. It is a rules-based screen — every verdict traces to a
named criterion and a number, and there is no opaque score anywhere in it.

What comes out is meant to be read by someone standing on the site:

    Strip footing
      Bearing            PASS     utilisation 0.68 of the net allowable
      Settlement         REVIEW   estimated 41 mm against a 50 mm limit
      Groundwater        PASS     water table 4.2 m below founding level
      Ground conditions  FAIL     expansive clay to 1.8 m under the footprint
      Constructability   GOOD

      Status: NOT RECOMMENDED AS FOUND — viable with the expansive clay removed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..record import CalculationRecord, Status
from ..sectors import get_sector
from ..standards import get_standard
from ..warnings import WarningList
from .steps import GroundFindings, Step, construction_steps, steps_as_dicts
from .types import FOUNDATION_TYPES


class Verdict(str, Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    FAIL = "FAIL"
    NO_DATA = "NO_DATA"


class CandidateStatus(str, Enum):
    PRELIMINARY_CANDIDATE = "PRELIMINARY_CANDIDATE"
    CANDIDATE_WITH_CONDITIONS = "CANDIDATE_WITH_CONDITIONS"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"
    REQUIRES_DATA = "REQUIRES_DATA"


@dataclass
class Criterion:
    name: str
    verdict: Verdict
    evidence: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "verdict": self.verdict.value, "evidence": self.evidence}


@dataclass
class Candidate:
    foundation_type: str
    label: str
    status: CandidateStatus
    criteria: list[Criterion] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    relative_cost: str = "moderate"
    steps: list[Step] = field(default_factory=list)

    @property
    def score(self) -> tuple[int, int, int]:
        """Rank key: fewest failures, then fewest reviews, then simplest system.

        Deliberately not a single opaque number. Two candidates that differ
        only in cost rank by cost; a candidate that fails a criterion never
        outranks one that does not, whatever else is in its favour.
        """
        fails = sum(1 for c in self.criteria if c.verdict is Verdict.FAIL)
        reviews = sum(1 for c in self.criteria if c.verdict in (Verdict.REVIEW, Verdict.NO_DATA))
        cost_rank = {"low": 0, "moderate": 1, "high": 2, "very high": 3}.get(
            self.relative_cost, 1
        )
        return (fails, reviews, cost_rank)

    def as_dict(self) -> dict[str, Any]:
        return {
            "foundation_type": self.foundation_type,
            "label": self.label,
            "status": self.status.value,
            "criteria": [c.as_dict() for c in self.criteria],
            "rationale": self.rationale,
            "conditions": self.conditions,
            "missing_data": self.missing_data,
            "relative_cost": self.relative_cost,
            "construction_steps": steps_as_dicts(self.steps),
        }


@dataclass(frozen=True)
class ScreeningInput:
    """Everything the screen reads. Anything absent produces NO_DATA, not a guess."""

    sector_id: str = "buildings_low_rise"
    #: Service load on the heaviest column, kN (or per metre run for a wall).
    service_load_kn: float | None = None
    #: Net allowable bearing pressure at the trial founding depth, kPa.
    net_allowable_kpa: float | None = None
    #: Footing size returned by the sizing calculation, m.
    required_footing_width_m: float | None = None
    #: Utilisation of the allowable pressure at that size.
    utilisation: float | None = None
    #: Total estimated settlement, mm.
    total_settlement_mm: float | None = None
    #: Typical column spacing, m — decides whether pads would overlap.
    column_spacing_m: float | None = None
    #: Plan footprint, m2.
    footprint_area_m2: float | None = None
    number_of_columns: int | None = None
    floors: int = 1
    #: Depth to a stratum competent enough to found on, m.
    competent_stratum_depth_m: float | None = None
    trial_founding_depth_m: float = 1.5
    #: Uplift or tension at the foundation, kN.
    uplift_kn: float | None = None
    findings: GroundFindings = field(default_factory=GroundFindings)
    standard_id: str | None = None


def _bearing_criterion(data: ScreeningInput) -> Criterion:
    if data.utilisation is None or data.net_allowable_kpa is None:
        return Criterion(
            "Bearing capacity", Verdict.NO_DATA,
            "No bearing capacity has been calculated — soil strength parameters are missing.",
        )
    if data.utilisation <= 0.85:
        return Criterion(
            "Bearing capacity", Verdict.PASS,
            f"Applied pressure is {data.utilisation:.0%} of the {data.net_allowable_kpa:.0f} kPa "
            "net allowable.",
        )
    if data.utilisation <= 1.0:
        return Criterion(
            "Bearing capacity", Verdict.REVIEW,
            f"Applied pressure is {data.utilisation:.0%} of the net allowable — within "
            "capacity but with little margin for variation across the site.",
        )
    return Criterion(
        "Bearing capacity", Verdict.FAIL,
        f"Applied pressure exceeds the net allowable ({data.utilisation:.0%} of it) at the "
        "size screened.",
    )


def _settlement_criterion(data: ScreeningInput, limit_mm: float) -> Criterion:
    if data.total_settlement_mm is None:
        return Criterion(
            "Settlement", Verdict.NO_DATA,
            "No settlement estimate — the soil modulus or the oedometer parameters are missing. "
            "On soft or compressible ground, settlement rather than bearing usually governs.",
        )
    s = data.total_settlement_mm
    if s <= 0.6 * limit_mm:
        return Criterion("Settlement", Verdict.PASS, f"Estimated {s:.0f} mm against a {limit_mm:.0f} mm limit.")
    if s <= limit_mm:
        return Criterion(
            "Settlement", Verdict.REVIEW,
            f"Estimated {s:.0f} mm against a {limit_mm:.0f} mm limit — acceptable in total, but "
            "differential settlement across the structure needs checking.",
        )
    return Criterion(
        "Settlement", Verdict.FAIL,
        f"Estimated {s:.0f} mm exceeds the {limit_mm:.0f} mm limit for this sector.",
    )


def _groundwater_criterion(data: ScreeningInput, deep: bool) -> Criterion:
    f = data.findings
    if f.groundwater_depth_m is None and not f.high_water_table:
        return Criterion(
            "Groundwater", Verdict.NO_DATA,
            "Groundwater was not observed or recorded. Excavation and flotation cannot be "
            "assessed without it.",
        )
    dw = f.groundwater_depth_m
    if dw is None:
        return Criterion("Groundwater", Verdict.REVIEW, "A high water table was reported but no depth was recorded.")
    below_base = dw - data.trial_founding_depth_m
    if below_base > 1.0:
        return Criterion("Groundwater", Verdict.PASS, f"Water table {below_base:.1f} m below founding level.")
    if deep:
        return Criterion(
            "Groundwater", Verdict.REVIEW,
            f"Water table at {dw:.1f} m. Boring below it needs casing or support fluid, which "
            "is normal for piling but adds cost.",
        )
    return Criterion(
        "Groundwater", Verdict.FAIL if below_base < 0 else Verdict.REVIEW,
        f"Water table at {dw:.1f} m is at or near the {data.trial_founding_depth_m:.1f} m "
        "founding level. Excavation will need dewatering and the bearing capacity is reduced "
        "by buoyancy.",
    )


def _ground_conditions_criterion(data: ScreeningInput, shallow: bool) -> Criterion:
    f = data.findings
    problems: list[str] = []
    if f.organic_or_peat:
        problems.append("organic soil or peat, which compresses for decades")
    if f.expansive_clay or f.swell_potential in ("HIGH", "VERY_HIGH"):
        depth = f" to about {f.black_cotton_depth_m:.1f} m" if f.black_cotton_depth_m else ""
        problems.append(f"expansive clay{depth}, which moves seasonally whatever the load")
    if f.collapsible_soil:
        problems.append("collapsible soil, which loses strength on wetting")
    if f.made_ground_depth_m:
        problems.append(f"made ground to about {f.made_ground_depth_m:.1f} m")

    if not problems:
        return Criterion("Ground conditions", Verdict.PASS, "No problem soils identified in the investigation.")
    joined = "; ".join(problems)
    if shallow:
        return Criterion("Ground conditions", Verdict.FAIL, f"Found {joined}. A shallow foundation on this as found will move.")
    return Criterion("Ground conditions", Verdict.REVIEW, f"Found {joined}. A deep foundation passes through it, but the shaft must be designed for it.")


def _excavation_criterion(data: ScreeningInput, foundation_type: str) -> Criterion:
    depth = data.competent_stratum_depth_m
    if depth is None:
        return Criterion(
            "Excavation depth", Verdict.NO_DATA,
            "Depth to a competent founding stratum is not established — the boreholes do not "
            "reach it or have not been logged.",
        )
    if foundation_type in ("strip", "pad", "combined", "raft", "ring_beam", "pad_and_chimney"):
        if depth <= 2.0:
            return Criterion("Excavation depth", Verdict.PASS, f"Competent stratum at {depth:.1f} m — within ordinary excavation.")
        if depth <= 3.5:
            return Criterion("Excavation depth", Verdict.REVIEW, f"Competent stratum at {depth:.1f} m — deep for a shallow foundation; excavation support and volume become significant.")
        return Criterion("Excavation depth", Verdict.FAIL, f"Competent stratum at {depth:.1f} m is too deep for an economic shallow foundation.")
    return Criterion("Excavation depth", Verdict.PASS, f"A deep foundation reaches the competent stratum at {depth:.1f} m by design.")


def _uplift_criterion(data: ScreeningInput, foundation_type: str) -> Criterion:
    if data.uplift_kn is None or data.uplift_kn <= 0:
        return Criterion("Uplift", Verdict.PASS, "No net uplift reported at the foundation.")
    good = foundation_type in ("pad_and_chimney", "bored_pile", "driven_pile", "ground_screw", "rock_anchor", "gravity_base", "raft")
    if good:
        return Criterion("Uplift", Verdict.REVIEW, f"{data.uplift_kn:.0f} kN of uplift must be verified against the resisting weight or shaft capacity.")
    return Criterion("Uplift", Verdict.FAIL, f"{data.uplift_kn:.0f} kN of uplift cannot be resisted economically by this foundation type.")


def _pads_would_overlap(data: ScreeningInput) -> bool:
    if data.required_footing_width_m is None or data.column_spacing_m is None:
        return False
    return data.required_footing_width_m > 0.5 * data.column_spacing_m


def screen_foundations(data: ScreeningInput) -> CalculationRecord:
    """Screen every foundation family this sector allows, and rank the candidates."""
    sector = get_sector(data.sector_id)
    standard = get_standard(data.standard_id)
    w = WarningList()
    candidates: list[Candidate] = []

    limit_mm = min(sector.settlement_limit_mm, standard.settlement_limit_mm)
    overlap = _pads_would_overlap(data)

    for ftype in sector.candidate_foundations:
        spec = FOUNDATION_TYPES.get(ftype)
        if spec is None:
            continue
        shallow = spec.family in ("shallow", "improvement")
        deep = spec.family == "deep"

        criteria = [
            _bearing_criterion(data),
            _settlement_criterion(data, limit_mm),
            _groundwater_criterion(data, deep),
            _ground_conditions_criterion(data, shallow and ftype != "ground_improvement_shallow"),
            _excavation_criterion(data, ftype),
            _uplift_criterion(data, ftype),
        ]
        criteria.append(
            Criterion("Constructability", Verdict.PASS, spec.buildability)
        )

        candidate = Candidate(
            foundation_type=ftype,
            label=spec.label,
            status=CandidateStatus.PRELIMINARY_CANDIDATE,
            criteria=criteria,
            relative_cost=spec.relative_cost,
        )

        # ---- rationale and conditions, stated in plain terms ----
        if ftype in ("pad", "combined") and overlap:
            candidate.criteria.append(Criterion(
                "Layout", Verdict.FAIL,
                f"A {data.required_footing_width_m:.2f} m pad at {data.column_spacing_m:.1f} m "
                "column spacing covers more than half the plan area. Pads that nearly touch "
                "are a raft built the expensive way.",
            ))
        if ftype == "raft":
            if overlap:
                candidate.rationale.append(
                    "Pads would cover more than half the footprint at this load and spacing, "
                    "which is the usual point at which a raft becomes both cheaper and stiffer."
                )
            if data.findings.expansive_clay:
                candidate.rationale.append(
                    "A stiff raft rides over seasonal ground movement instead of following it "
                    "footing by footing, which is why it is a standard answer on expansive clay."
                )
            if data.total_settlement_mm and data.total_settlement_mm > 0.6 * limit_mm:
                candidate.rationale.append(
                    "A raft spreads the load over the whole footprint, reducing the bearing "
                    "pressure and the differential settlement between one column and the next."
                )
        if ftype == "ground_improvement_shallow":
            depth = data.competent_stratum_depth_m
            if depth is not None and depth <= 3.0:
                candidate.rationale.append(
                    f"The weak material is only about {depth:.1f} m thick, so excavating it out "
                    "and replacing it with compacted fill is usually cheaper than piling "
                    "through it — and needs no piling plant on site."
                )
            elif depth is not None:
                candidate.criteria.append(Criterion(
                    "Treatment depth", Verdict.FAIL,
                    f"The weak layer extends to {depth:.1f} m. Excavating and replacing that "
                    "depth across the footprint is rarely economic.",
                ))
            candidate.conditions.append(
                "The improved layer must be proved by testing to the bearing pressure the "
                "design assumes — the calculation is only valid on ground that was tested."
            )
        if deep:
            candidate.rationale.append(
                "A deep foundation transfers load past the weak material to a competent "
                "stratum, so the problem soil above no longer carries the structure."
            )
            candidate.conditions.append(
                "Pile capacity must be confirmed by a load test or, for driven piles, by an "
                "agreed set criterion on every pile."
            )
        if ftype == "piled_raft":
            candidate.conditions.append(
                "The load split between raft and piles must be modelled, not assumed. It "
                "needs a stiffness-based analysis and good investigation data."
            )

        # ---- status from the criteria, with no hidden weighting ----
        fails = [c for c in candidate.criteria if c.verdict is Verdict.FAIL]
        no_data = [c for c in candidate.criteria if c.verdict is Verdict.NO_DATA]
        reviews = [c for c in candidate.criteria if c.verdict is Verdict.REVIEW]

        ground_fail = any(c.name == "Ground conditions" and c.verdict is Verdict.FAIL for c in candidate.criteria)
        if fails:
            candidate.status = CandidateStatus.NOT_RECOMMENDED
            if ground_fail and ftype in ("strip", "pad", "combined", "raft"):
                candidate.conditions.append(
                    "Viable if the problem soil is removed and replaced with compacted "
                    "engineered fill first, or if the foundation is taken below it. "
                    "See the ground improvement option."
                )
                candidate.status = CandidateStatus.CANDIDATE_WITH_CONDITIONS
        elif no_data:
            candidate.status = CandidateStatus.REQUIRES_DATA
        elif reviews:
            candidate.status = CandidateStatus.CANDIDATE_WITH_CONDITIONS
        candidate.missing_data = [c.evidence for c in no_data]

        candidate.steps = construction_steps(
            ftype, findings=data.findings, sector_id=data.sector_id
        )
        candidates.append(candidate)

    candidates.sort(key=lambda c: c.score)

    if not any(c.status in (CandidateStatus.PRELIMINARY_CANDIDATE, CandidateStatus.CANDIDATE_WITH_CONDITIONS) for c in candidates):
        w.critical(
            "NO_VIABLE_CANDIDATE",
            "No foundation option screened viable on the data supplied. Either the ground "
            "data is too thin to screen against, or this site needs a specialist solution. "
            "A geotechnical engineer should look at it before the design goes further.",
        )
    if any(c.status is CandidateStatus.REQUIRES_DATA for c in candidates):
        w.warn(
            "SCREENING_INCOMPLETE",
            "Some options could not be screened because required data is missing. The "
            "candidates listed are provisional until that data is supplied.",
        )
    w.warn(
        "CANDIDATES_NOT_A_SELECTION",
        "These are CANDIDATE options, not a foundation design. Selecting between them, "
        "sizing the chosen system and detailing it are engineering decisions that require a "
        "qualified engineer and the site investigation data this screen has listed.",
    )

    return CalculationRecord(
        calculation_type="foundation_screening",
        method="rules_based_screening",
        status=Status.CALCULATED,
        inputs={
            "sector": sector.id,
            "service_load_kn": data.service_load_kn,
            "net_allowable_kpa": data.net_allowable_kpa,
            "required_footing_width_m": data.required_footing_width_m,
            "utilisation": data.utilisation,
            "total_settlement_mm": data.total_settlement_mm,
            "column_spacing_m": data.column_spacing_m,
            "competent_stratum_depth_m": data.competent_stratum_depth_m,
            "trial_founding_depth_m": data.trial_founding_depth_m,
            "uplift_kn": data.uplift_kn,
            "findings": data.findings.__dict__,
        },
        results={
            "sector": {
                "id": sector.id,
                "label": sector.label,
                "governing_checks": list(sector.governing_checks),
                "settlement_limit_mm": limit_mm,
                "required_investigation": list(sector.required_investigation),
                "standards": list(sector.standards),
            },
            "candidates": [c.as_dict() for c in candidates],
            "candidate_count": len(candidates),
        },
        warnings=w,
        standard_id=standard.id,
        standard_edition=standard.edition,
    )
