"""The report, as a structured document rather than a rendered file.

Spec sections 41-42. The renderer (PDF, HTML, DOCX) is a separate concern;
what matters here is that the document always carries the same 23 sections in
the same order, always states its limitations, always shows where every
number came from, and is versioned as a revision rather than overwritten.

The banner is the part that must never be optional:

    PRELIMINARY - ENGINEER REVIEW REQUIRED

It comes off only when a qualified reviewer has signed the project through
the review workflow, which lives outside this engine. Nothing in the engine
can clear it on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ..record import CalculationRecord
from ..sectors import get_sector
from ..standards import METHOD_REFERENCES, get_standard
from ..version import ENGINE_VERSION

PRELIMINARY_BANNER = "PRELIMINARY - ENGINEER REVIEW REQUIRED"
REVIEWED_BANNER = "REVIEWED AND SIGNED BY A QUALIFIED ENGINEER"

#: The section order, fixed. Spec section 41.
SECTION_ORDER: tuple[str, ...] = (
    "Cover",
    "Project information",
    "Client",
    "Site location",
    "Structure description",
    "Investigation information",
    "Soil photographs",
    "AI observations",
    "Borehole logs",
    "Soil profile",
    "Groundwater",
    "Field tests",
    "Laboratory tests",
    "Structural and load assumptions",
    "Bearing capacity calculations",
    "Settlement assessment",
    "Foundation candidates",
    "Recommended construction sequence",
    "Limitations",
    "Recommendations for further investigation",
    "Engineer review",
    "Calculation appendix",
    "References",
    "Revision history",
)

#: Standing limitations. Every report carries all of these, always.
STANDING_LIMITATIONS: tuple[str, ...] = (
    "This report is a preliminary desk and screening assessment produced by software. "
    "It is not a geotechnical site investigation and does not replace one.",
    "Visual and AI-assisted soil classification describes what is visible. It does not "
    "establish bearing capacity, shear strength, density or groundwater level, and no "
    "measured value in this report was derived from a photograph.",
    "Calculated values are only as good as the data entered. Where a parameter was "
    "correlated or assumed rather than measured, the provenance table says so, and the "
    "result should be treated as an order-of-magnitude screen.",
    "Ground conditions vary between investigation points. Conditions encountered during "
    "construction may differ from those reported here, and the founding stratum must be "
    "inspected and confirmed when the excavation is open.",
    "This report does not certify any structure as safe, does not constitute a foundation "
    "design, and does not authorise construction. Final foundation design must be carried "
    "out and sealed by an engineer registered in the project's jurisdiction.",
)


@dataclass
class ReportSection:
    title: str
    body: str = ""
    items: list[str] = field(default_factory=list)
    table: list[dict[str, Any]] = field(default_factory=list)
    calculations: list[CalculationRecord] = field(default_factory=list)
    #: Set when a section has no content because the data was never collected.
    absent_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body": self.body,
            "items": self.items,
            "table": self.table,
            "calculations": [c.as_dict() for c in self.calculations],
            "absent_reason": self.absent_reason,
        }


@dataclass
class Review:
    reviewer_name: str
    registration_number: str
    status: str  # APPROVED / REJECTED / COMMENTS
    comments: str
    signed_at: str


@dataclass
class GeotechnicalReport:
    project_name: str
    client_name: str | None
    site_location: str | None
    sector_id: str
    standard_id: str
    revision: int = 1
    generated_on: str = field(default_factory=lambda: date.today().isoformat())
    ai_model: str | None = None
    sections: list[ReportSection] = field(default_factory=list)
    review: Review | None = None
    engine_version: str = ENGINE_VERSION

    @property
    def banner(self) -> str:
        if self.review and self.review.status == "APPROVED":
            return REVIEWED_BANNER
        return PRELIMINARY_BANNER

    def section(self, title: str) -> ReportSection:
        for s in self.sections:
            if s.title == title:
                return s
        s = ReportSection(title)
        self.sections.append(s)
        return s

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "client_name": self.client_name,
            "site_location": self.site_location,
            "sector": self.sector_id,
            "standard": self.standard_id,
            "revision": self.revision,
            "generated_on": self.generated_on,
            "engine_version": self.engine_version,
            "ai_model": self.ai_model,
            "banner": self.banner,
            "sections": [s.as_dict() for s in self.sections],
            "review": self.review.__dict__ if self.review else None,
        }


def build_report(
    *,
    project_name: str,
    client_name: str | None = None,
    site_location: str | None = None,
    sector_id: str = "buildings_low_rise",
    standard_id: str = "eurocode",
    revision: int = 1,
    bearing: CalculationRecord | None = None,
    sizing: CalculationRecord | None = None,
    settlement: list[CalculationRecord] | None = None,
    loads: CalculationRecord | None = None,
    screening: CalculationRecord | None = None,
    borehole_logs: list[dict[str, Any]] | None = None,
    ai_observations: list[dict[str, Any]] | None = None,
    ai_model: str | None = None,
    review: Review | None = None,
    data_gaps: list[str] | None = None,
) -> GeotechnicalReport:
    """Assemble the full report from whatever the project actually has.

    Sections with no data are not omitted. They appear with an
    ``absent_reason``, because a missing borehole log is itself a finding and
    hiding the gap is how a screening report gets mistaken for an
    investigation.
    """
    sector = get_sector(sector_id)
    standard = get_standard(standard_id)
    report = GeotechnicalReport(
        project_name=project_name,
        client_name=client_name,
        site_location=site_location,
        sector_id=sector.id,
        standard_id=standard.id,
        revision=revision,
        ai_model=ai_model,
        review=review,
    )
    for title in SECTION_ORDER:
        report.sections.append(ReportSection(title))

    report.section("Cover").body = (
        f"GeoFatali geotechnical and foundation assessment\n"
        f"Project: {project_name}\n"
        f"Revision: {revision:02d}\n"
        f"Engine version: {ENGINE_VERSION}\n"
        f"{report.banner}"
    )
    report.section("Project information").table = [
        {"field": "Sector", "value": sector.label},
        {"field": "Design standard", "value": f"{standard.name} ({standard.edition})"},
        {"field": "Jurisdiction", "value": standard.jurisdiction},
        {"field": "Engine version", "value": ENGINE_VERSION},
    ]
    report.section("Client").body = client_name or ""
    if not client_name:
        report.section("Client").absent_reason = "No client was recorded on the project."
    report.section("Site location").body = site_location or ""
    if not site_location:
        report.section("Site location").absent_reason = (
            "No site location or coordinates were recorded. Regional ground conditions and "
            "the applicable authority cannot be established without them."
        )

    inv = report.section("Investigation information")
    inv.items = list(sector.required_investigation)
    inv.body = (
        f"What an adequate investigation for {sector.label.lower()} must include. Anything "
        "on this list that was not done is a limitation on everything that follows."
    )

    bh = report.section("Borehole logs")
    if borehole_logs:
        bh.table = borehole_logs
    else:
        bh.absent_reason = (
            "No borehole or trial pit logs were entered. Every strength parameter used in "
            "this report is therefore correlated or assumed, not measured in the ground."
        )

    ai = report.section("AI observations")
    if ai_observations:
        ai.table = ai_observations
        ai.body = (
            "Visual observations from soil photographs. These are AI_VISUAL_CLASSIFICATION "
            "records: a description of what is visible, with a stated confidence. They are "
            "not measurements and were not used as measured values in any calculation."
        )
    else:
        ai.absent_reason = "No soil images were analysed for this project."

    if loads:
        report.section("Structural and load assumptions").calculations.append(loads)
    else:
        report.section("Structural and load assumptions").absent_reason = (
            "No structural loads were supplied or estimated."
        )

    bc = report.section("Bearing capacity calculations")
    if bearing:
        bc.calculations.append(bearing)
    if sizing:
        bc.calculations.append(sizing)
    if not bearing and not sizing:
        bc.absent_reason = (
            "Bearing capacity was not calculated. The soil strength parameters required "
            "(cohesion and friction angle, or undrained shear strength) were not available."
        )

    st = report.section("Settlement assessment")
    if settlement:
        st.calculations.extend(settlement)
    else:
        st.absent_reason = (
            "Settlement was not assessed. On compressible ground this is the check that "
            "governs, and a bearing capacity result alone does not demonstrate adequacy."
        )

    fc = report.section("Foundation candidates")
    seq = report.section("Recommended construction sequence")
    if screening:
        fc.calculations.append(screening)
        candidates = screening.results.get("candidates", [])
        fc.items = [f"{c['label']} — {c['status']}" for c in candidates]
        fc.body = (
            "Candidate foundation systems, screened against the criteria shown. This is a "
            "screen, not a selection: choosing between these options is an engineering "
            "decision."
        )
        if candidates:
            top = candidates[0]
            seq.body = (
                f"Construction sequence for the highest-ranked candidate, {top['label']}. "
                "Steps marked as hold points are where work stops until an engineer has "
                "inspected. Steps that were added because of the ground conditions found on "
                "this site name what triggered them."
            )
            seq.table = top["construction_steps"]
    else:
        fc.absent_reason = "Foundation screening was not run."
        seq.absent_reason = "No construction sequence — no foundation option has been screened."

    lim = report.section("Limitations")
    lim.items = list(STANDING_LIMITATIONS)

    rec = report.section("Recommendations for further investigation")
    # Warnings raised by the correlations happen before any CalculationRecord
    # exists, so the caller passes them in rather than losing them.
    gaps: list[str] = list(data_gaps or [])
    for calc in [c for c in (bearing, sizing, loads, screening) if c] + list(settlement or []):
        for warning in calc.warnings:
            if warning.severity.value in ("CRITICAL", "WARNING"):
                gaps.append(warning.message)
    rec.items = list(dict.fromkeys(gaps)) or [
        "No outstanding data gaps were flagged by the calculations run for this project."
    ]
    rec.body = (
        "Every warning raised by the calculations, gathered in one place. Each one is "
        "something to measure, confirm or decide before this assessment becomes a design."
    )

    rv = report.section("Engineer review")
    if review:
        rv.table = [
            {"field": "Reviewer", "value": review.reviewer_name},
            {"field": "Registration", "value": review.registration_number},
            {"field": "Status", "value": review.status},
            {"field": "Signed", "value": review.signed_at},
            {"field": "Comments", "value": review.comments},
        ]
    else:
        rv.absent_reason = (
            "This report has not been reviewed by an engineer. It carries the preliminary "
            "banner and must not be used as a basis for construction."
        )

    app = report.section("Calculation appendix")
    app.calculations = [c for c in (loads, bearing, sizing, screening) if c] + list(settlement or [])
    app.body = (
        "Every calculation in full: inputs, method, standard, engine version, results and "
        "warnings. Each one is reproducible from the inputs recorded here."
    )

    refs = report.section("References")
    used_methods = {c.method for c in app.calculations}
    refs.items = [
        f"{METHOD_REFERENCES[m].title} — {METHOD_REFERENCES[m].citation}"
        for m in sorted(used_methods)
        if m in METHOD_REFERENCES
    ] + [f"Design standard: {standard.name} ({standard.edition}) — {standard.reference}"] + [
        f"Sector standards: {', '.join(sector.standards)}"
    ]

    report.section("Revision history").table = [
        {
            "revision": f"{revision:02d}",
            "date": report.generated_on,
            "engine_version": ENGINE_VERSION,
            "ai_model": ai_model or "not used",
            "status": report.banner,
        }
    ]
    return report
