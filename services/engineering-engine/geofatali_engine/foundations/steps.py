"""What to actually do on site, in order.

This is the part of GeoFatali that a site agent in Kitengela or a technician
on a tower line can use directly. The calculations say *which* foundation is
a candidate; this says *how it gets built*, step by step, with the hold points
where work stops until something is checked.

The steps are not generic boilerplate. They are assembled from three things:

  1. the foundation type's own construction sequence;
  2. the ground conditions found — expansive clay, a high water table,
     aggressive sulphates, collapsible ash, shallow rock each insert their own
     steps in the right place in the sequence;
  3. the sector — a tank pad gets a hydrotest settlement survey, a tower base
     gets a backfill compaction hold point, a road formation gets a proof roll.

Every step that matters carries a ``verify`` line: what has to be true before
the next step starts. A step marked ``hold_point`` is one where work stops
until an engineer has seen it — founding-level inspection being the one that
saves the most projects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..sectors import get_sector
from .types import FOUNDATION_TYPES


@dataclass(frozen=True)
class Step:
    order: int
    title: str
    detail: str
    #: Work stops here until an engineer or the authority has inspected.
    hold_point: bool = False
    #: What must be true before moving on.
    verify: str | None = None
    #: Why this step is in the list for THIS site, when it was inserted by a
    #: ground condition rather than being part of the standard sequence.
    triggered_by: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "title": self.title,
            "detail": self.detail,
            "hold_point": self.hold_point,
            "verify": self.verify,
            "triggered_by": self.triggered_by,
        }


@dataclass(frozen=True)
class GroundFindings:
    """What the investigation actually found, in the terms the steps react to."""

    expansive_clay: bool = False
    swell_potential: str = "UNKNOWN"      # LOW / MEDIUM / HIGH / VERY_HIGH
    high_water_table: bool = False
    groundwater_depth_m: float | None = None
    aggressive_ground: bool = False        # sulphates, chlorides, low pH
    collapsible_soil: bool = False
    soft_layer_depth_m: float | None = None
    rock_depth_m: float | None = None
    made_ground_depth_m: float | None = None
    organic_or_peat: bool = False
    seismic_pga_g: float | None = None
    black_cotton_depth_m: float | None = None


# ───────────────────── the base sequences, per foundation ─────────────────────

def _strip_or_pad_sequence(is_strip: bool) -> list[tuple[str, str, bool, str | None]]:
    unit = "trench" if is_strip else "pit"
    element = "strip footing" if is_strip else "pad footing"
    return [
        ("Set out and confirm levels",
         f"Set out the {element} lines from the approved drawings and establish a datum peg "
         "that will survive the excavation. Check the setting out against the site boundary "
         "before any digging starts.",
         False,
         "Setting out checked against the drawing and the boundary, and signed off."),
        (f"Excavate the {unit} to founding level",
         f"Excavate to the design founding depth. Keep the sides safe: batter them back or "
         "support them, and never let anyone work in an unsupported excavation over 1.2 m deep.",
         False,
         "Depth checked against the datum, not against ground level, which varies."),
        ("Inspect the founding stratum",
         "The engineer inspects the bottom of the excavation and confirms it is the stratum "
         "the design assumed. Take a hand penetrometer or vane reading and photograph the "
         "face. If the ground is not what the borehole predicted, stop and re-assess — this "
         "is the single most valuable half hour on the project.",
         True,
         "Founding stratum matches the design assumption, recorded with photographs and a "
         "level. Any difference is referred back to the designer before concreting."),
        ("Trim, clean and de-water",
         "Remove all loose and softened material from the base by hand. Do not leave "
         "puddled water or sludge — concrete placed on soft slurry does not bear on the "
         "stratum that was inspected.",
         False,
         "Base clean, firm and free of standing water immediately before blinding."),
        ("Place blinding concrete",
         "Place 50-75 mm of lean concrete over the whole base to protect the formation and "
         "give a clean surface to set out and fix steel on.",
         False,
         "Blinding covers the full base and is level."),
        ("Fix reinforcement with correct cover",
         "Fix the reinforcement to the schedule, on proper spacers. Cover is what protects "
         "the steel for the life of the structure and it is the most commonly cut corner on "
         "site — check it on every bar mat, not on a sample.",
         True,
         "Bar sizes, spacing and cover checked against the schedule and signed off before "
         "concrete is ordered."),
        ("Cast the footing",
         f"Cast the {element} in one continuous operation to the design level. Compact with "
         "a poker, not by tamping. Record the concrete grade, the batch and the cube samples.",
         False,
         "Cubes taken and identified; pour record completed."),
        ("Cure and protect",
         "Keep the concrete continuously damp for at least seven days. In hot, dry or windy "
         "conditions cover it — concrete that dries out in the first days never reaches the "
         "strength that was specified.",
         False,
         "Curing maintained for the full period and recorded."),
        ("Backfill in compacted layers",
         "Backfill in layers no thicker than 200 mm, each one compacted. Uncompacted "
         "backfill settles, cracks the ground slab and lets water down to the footing.",
         False,
         "Each layer compacted and tested where the specification requires it."),
    ]


_RAFT_SEQUENCE = [
    ("Strip and set out the full raft area",
     "Strip topsoil and all vegetable matter across the whole raft footprint plus a working "
     "margin. A raft only works as a single stiff element, so the preparation has to be "
     "uniform across the entire area.",
     False,
     "Topsoil and soft spots removed across the full area, not only under the walls."),
    ("Excavate and proof roll the formation",
     "Excavate to formation and proof roll it with a loaded vehicle. Watch for soft spots "
     "that pump or rut — they are the places the raft will settle differentially.",
     True,
     "Proof roll witnessed; every soft spot dug out and replaced with compacted material."),
    ("Place and compact the sub-base",
     "Place granular sub-base in compacted layers to the design thickness, and test the "
     "compaction. This layer is what makes the bearing pressure uniform under the slab.",
     False,
     "Compaction tests pass at the specified frequency across the whole area."),
    ("Lay the damp-proof membrane",
     "Lay the membrane over the blinding with lapped and taped joints, turned up at the "
     "edges. Repair every puncture before steel fixing starts.",
     False,
     "Membrane continuous, lapped and undamaged."),
    ("Fix reinforcement, top and bottom",
     "Fix both mats with correct cover and proper chairs. A raft carries hogging and sagging "
     "moments, so both mats matter and the top steel is the one most often displaced by "
     "traffic during the pour.",
     True,
     "Both mats checked for size, spacing, laps and cover before the pour is booked."),
    ("Plan and cast the pour",
     "Agree the pour sequence, construction joints and the concrete supply rate in advance. "
     "A raft is a large continuous pour; running out of concrete halfway creates a cold "
     "joint where none was designed.",
     False,
     "Pour plan agreed, supply confirmed, standby vibrator and generator on site."),
    ("Finish, cure and protect",
     "Power float to the specified finish, then cure continuously. Thick slabs also need "
     "protecting from differential temperature in the first days.",
     False,
     "Curing regime maintained; no early-age cracking recorded."),
]

_BORED_PILE_SEQUENCE = [
    ("Confirm the piling platform",
     "Build and certify a working platform that will carry the rig. Rig overturning on an "
     "inadequate platform is the leading cause of serious injury in piling.",
     True,
     "Platform designed, built and certified for the specific rig."),
    ("Set out pile positions",
     "Set out every pile and record its position. Tolerances on position and verticality are "
     "tight because eccentricity at the pile head goes straight into the pile cap design.",
     False,
     "Positions surveyed and recorded against the drawing."),
    ("Install temporary casing",
     "Case through made ground, loose material and any unstable layer so the bore does not "
     "collapse and the concrete is not contaminated.",
     False,
     "Casing seated in stable ground below the unstable strata."),
    ("Bore to design toe level",
     "Bore to the design level, keeping the bore stable with casing or support fluid below "
     "the water table. Log the spoil continuously against the borehole record — the bore is "
     "an investigation in its own right.",
     True,
     "Founding stratum confirmed at toe level against the borehole log; any difference "
     "referred to the designer before concreting."),
    ("Clean the base",
     "Remove debris and sediment from the base. Soft spoil left at the toe is exactly the "
     "material the end bearing was calculated to exclude.",
     True,
     "Base cleanliness verified before the reinforcement cage is lowered."),
    ("Lower the reinforcement cage",
     "Lower the cage centrally with spacers so cover is maintained all round, and hold it "
     "against flotation during concreting.",
     False,
     "Cage central, correct level, adequately restrained."),
    ("Concrete by tremie, bottom up",
     "Place concrete by tremie with the pipe kept buried in the fresh concrete throughout. "
     "Record the concrete volume against the theoretical volume as the pour proceeds — a "
     "shortfall means a defect, and it can only be seen at the time.",
     False,
     "Concrete volume plotted against theoretical volume; over-break and shortfall explained."),
    ("Trim to cut-off and test",
     "Break down to sound concrete at cut-off level and carry out integrity testing on the "
     "agreed proportion of piles, with static or dynamic load testing where specified.",
     True,
     "Integrity and load test results accepted before the pile cap is cast."),
]

_DRIVEN_PILE_SEQUENCE = [
    ("Confirm the platform and pile set criteria",
     "Agree the driving criteria — set per blow, or final torque for a screw — with the "
     "designer before driving begins. The criterion is how capacity is confirmed on every "
     "pile, so it cannot be decided after the fact.",
     True,
     "Driving criteria issued in writing by the designer."),
    ("Drive trial piles and test them",
     "Drive trial piles at representative locations and load test them. The trial proves "
     "both the capacity and the driveability before the main works are committed.",
     True,
     "Trial pile load test result accepted."),
    ("Drive the working piles",
     "Drive each pile to the agreed set or depth. Record the driving log for every pile: the "
     "log is the test certificate for that pile.",
     False,
     "Driving log complete for every pile, with any early refusal flagged."),
    ("Deal with refusals and short piles",
     "Do not accept a pile that refused high without referring it back. Early refusal usually "
     "means an obstruction or shallow rock, not capacity.",
     True,
     "Every non-conforming pile individually assessed and dispositioned."),
    ("Trim and cap",
     "Trim to cut-off, check position and verticality against tolerance, and design the cap "
     "for any eccentricity that was actually built.",
     False,
     "As-built positions surveyed; cap design confirmed against them."),
]

_GROUND_IMPROVEMENT_SEQUENCE = [
    ("Confirm the extent of the weak layer",
     "Establish the depth and plan extent of the material to be removed or treated, by trial "
     "pits across the footprint. Treating an area that was assumed rather than proved is how "
     "improvement works end up failing at the edges.",
     True,
     "Depth and extent proved on a grid, not interpolated from two boreholes."),
    ("Excavate or treat to the design depth",
     "Excavate the weak material and cart it away, or mix in the stabilising agent, to the "
     "full design depth and at least the design distance beyond the footing edge — usually "
     "the depth of the treatment, taken as a 45-degree spread.",
     False,
     "Excavation or treatment extends beyond the loaded area by the design margin."),
    ("Inspect the exposed formation",
     "Inspect and test the formation exposed beneath the removed material and confirm it is "
     "the competent layer the design relies on.",
     True,
     "Formation tested (DCP, plate or penetrometer) and accepted."),
    ("Place engineered fill in compacted layers",
     "Place approved fill in layers no thicker than 200-250 mm, each compacted to the "
     "specified density at the specified moisture content. Compaction is a moisture problem "
     "as much as an energy problem.",
     False,
     "Field density tests pass at the specified frequency, layer by layer."),
    ("Prove the improved layer",
     "Test the finished platform by plate load test, DCP or nuclear density to demonstrate "
     "that the improved ground achieves the design bearing pressure.",
     True,
     "Test results meet or exceed the design bearing pressure used in the calculation."),
    ("Build the shallow foundation on the improved layer",
     "Construct the strip, pad or raft on the proved platform following its own sequence.",
     False,
     None),
]

_PAD_AND_CHIMNEY_SEQUENCE = [
    ("Set out from the tower centre",
     "Set out each leg from the tower centre and the line direction, not from leg to leg. "
     "Errors compound around the base and the steelwork will not fit.",
     True,
     "Diagonals and leg spacing checked against the tower drawing."),
    ("Excavate to founding level",
     "Excavate the full block, keeping the sides as near vertical as the ground safely allows "
     "so the undisturbed soil frustum above the pad is preserved. That frustum is the uplift "
     "resistance.",
     False,
     "Excavation profile recorded; over-excavation reported as it reduces uplift capacity."),
    ("Inspect the founding stratum",
     "Confirm the bearing stratum and the soil that will provide uplift resistance.",
     True,
     "Stratum confirmed against the investigation record."),
    ("Cast the pad and chimney with the stub set",
     "Cast the pad, then the chimney, with the leg stub held in a template to the correct "
     "level, lean and orientation. Once the concrete has set, the stub position is permanent.",
     True,
     "Stub level, lean and orientation surveyed and accepted before concrete sets."),
    ("Backfill in compacted layers — this is the uplift design",
     "Backfill in 200 mm layers, each compacted to the specified density. The uplift capacity "
     "was calculated on the weight of properly compacted soil. Loose backfill is the most "
     "common cause of tower foundation pull-out.",
     True,
     "Density tests on the backfill pass at the specified frequency."),
    ("Reinstate and protect against erosion",
     "Reinstate the surface, grade so water runs away from the block, and protect against "
     "scour. A gully cutting past a tower leg removes the uplift resistance silently.",
     False,
     "Surface graded away from the foundation; erosion protection in place."),
]

_GRAVITY_BASE_SEQUENCE = [
    ("Prepare and prove the formation",
     "Excavate to founding level and prove the formation across the entire base — a gravity "
     "base is governed by rotational stiffness, so a soft patch on one side matters far more "
     "than the average bearing pressure.",
     True,
     "Plate load or equivalent testing across the base area, not at a single point."),
    ("Place blinding and set the anchor cage or bolt cage",
     "Set the anchor assembly to survey control. Level and orientation tolerances are very "
     "tight, and nothing can be adjusted after the pour.",
     True,
     "Anchor cage position, level and orientation surveyed and accepted."),
    ("Fix reinforcement",
     "Fix the heavy radial and circumferential reinforcement with correct cover, keeping "
     "access for the poker crews during the pour.",
     True,
     "Reinforcement and cover checked; pour access maintained."),
    ("Cast in a single continuous pour",
     "Cast continuously, controlling placement temperature and the temperature differential "
     "across the section. Mass concrete cracks from internal heat, not from load.",
     False,
     "Pour continuous; temperature monitoring within the specified differential."),
    ("Cure, backfill and monitor",
     "Cure fully, backfill in compacted layers to provide the design overburden weight, then "
     "install the settlement and tilt monitoring points the design requires.",
     True,
     "Backfill weight achieved; monitoring baseline recorded before commissioning."),
]

_RING_BEAM_SEQUENCE = [
    ("Prepare and prove the tank formation",
     "Strip and prove the formation across the full tank diameter. The stress under a tank "
     "reaches deeper than under a building, so both the near-surface and deeper layers matter.",
     True,
     "Formation proved across the whole diameter."),
    ("Construct the ring beam",
     "Construct the reinforced ring to tight level tolerance. The shell is welded to what the "
     "ring gives it; an out-of-level ring distorts the shell permanently.",
     True,
     "Ring level surveyed at close intervals around the circumference."),
    ("Place and compact the fill pad",
     "Place the granular pad inside the ring in compacted layers, then finish with the "
     "bitumen sand or specified layer under the tank floor.",
     False,
     "Compaction tests pass; finished level and camber within tolerance."),
    ("Hydrotest with a settlement survey",
     "Fill the tank in stages with water, surveying settlement around the circumference at "
     "each stage. This is the load test of the foundation and the only chance to find "
     "differential settlement before the tank goes into service.",
     True,
     "Settlement within the design limit and acceptably uniform around the shell."),
]

_SUBGRADE_SEQUENCE = [
    ("Strip and expose the subgrade",
     "Strip topsoil and all vegetable matter to formation level along the full width and "
     "length of the works.",
     False,
     "Formation exposed and free of organic material."),
    ("Test the subgrade in place",
     "Carry out DCP or in-situ CBR testing at the specified chainage intervals. The pavement "
     "thickness is designed from these numbers, so a gap in the testing is a gap in the design.",
     True,
     "Test results recorded at every specified interval and compared with the design CBR."),
    ("Proof roll",
     "Proof roll the formation with a loaded vehicle and mark every area that deflects, ruts "
     "or pumps.",
     True,
     "Proof roll witnessed and all failing areas marked for treatment."),
    ("Treat the failing areas",
     "Dig out and replace, or stabilise with lime or cement, every area that failed. Lime "
     "suits plastic clay; cement suits granular and low-plasticity material.",
     False,
     "Treated areas retested and passing."),
    ("Place the capping and sub-base",
     "Place capping and sub-base in compacted layers to the design thickness, testing "
     "compaction and level on each layer.",
     False,
     "Layer thickness, density and level all within specification."),
]

_GROUND_SCREW_SEQUENCE = [
    ("Establish the torque-to-capacity relationship",
     "Install trial screws and load test them to set the installation torque that corresponds "
     "to the required capacity. Torque is the acceptance criterion for every subsequent pile.",
     True,
     "Trial load tests completed and the torque criterion issued in writing."),
    ("Survey and set out the array",
     "Set out positions across the array. Position tolerance matters because the table "
     "structure above has limited adjustment.",
     False,
     "Positions set out and recorded."),
    ("Install to the torque criterion",
     "Screw each pile to the required depth AND the required torque. Record both for every "
     "pile — a pile that reached depth without reaching torque has not reached capacity.",
     False,
     "Installation record complete for every pile, with depth and final torque."),
    ("Deal with refusals",
     "Where a screw refuses early on rock or obstruction, refer it for a local redesign - "
     "usually a shorter screw at higher torque, a predrill, or a ballast block.",
     True,
     "Every refusal individually dispositioned."),
    ("Verify a sample by pull-out test",
     "Pull-out test the specified proportion of installed piles, since uplift usually governs "
     "a solar foundation.",
     True,
     "Pull-out test results meet the design uplift capacity."),
]

_GENERIC_SEQUENCE = [
    ("Confirm the design basis on site",
     "Before anything is built, confirm that the ground conditions actually exposed match the "
     "investigation the design was based on.",
     True,
     "Exposed conditions match the design assumptions, or the designer has been informed."),
    ("Construct to the approved drawings and specification",
     "Build to the issued-for-construction drawings, with the material testing and inspection "
     "regime the specification requires.",
     False,
     "Inspection and test plan followed and records kept."),
    ("Test and record",
     "Carry out the acceptance testing for this foundation type and retain the records as "
     "part of the handover documentation.",
     True,
     "Acceptance criteria met and recorded."),
]

_SEQUENCES: dict[str, list[tuple[str, str, bool, str | None]]] = {
    "strip": _strip_or_pad_sequence(True),
    "pad": _strip_or_pad_sequence(False),
    "combined": _strip_or_pad_sequence(False),
    "raft": _RAFT_SEQUENCE,
    "piled_raft": _BORED_PILE_SEQUENCE + _RAFT_SEQUENCE,
    "bored_pile": _BORED_PILE_SEQUENCE,
    "driven_pile": _DRIVEN_PILE_SEQUENCE,
    "ground_improvement_shallow": _GROUND_IMPROVEMENT_SEQUENCE,
    "subgrade_improvement": _SUBGRADE_SEQUENCE,
    "pad_and_chimney": _PAD_AND_CHIMNEY_SEQUENCE,
    "gravity_base": _GRAVITY_BASE_SEQUENCE,
    "ring_beam": _RING_BEAM_SEQUENCE,
    "ground_screw": _GROUND_SCREW_SEQUENCE,
    "rock_socket": _BORED_PILE_SEQUENCE,
}


# ───────────────── ground-condition steps, inserted where they belong ─────────────────

def _condition_steps(
    findings: GroundFindings, foundation_type: str
) -> tuple[list[tuple[str, str, bool, str | None, str]], list[tuple[str, str, bool, str | None, str]]]:
    """Steps to insert before and after the standard sequence."""
    before: list[tuple[str, str, bool, str | None, str]] = []
    after: list[tuple[str, str, bool, str | None, str]] = []
    shallow = foundation_type in (
        "strip", "pad", "combined", "raft", "ring_beam", "pad_and_chimney", "gravity_base"
    )

    if findings.expansive_clay or findings.swell_potential in ("HIGH", "VERY_HIGH"):
        depth = findings.black_cotton_depth_m
        depth_text = f"about {depth:.1f} m" if depth else "the depth proved by the trial pits"
        if shallow:
            before.append((
                "Remove or isolate the expansive clay",
                f"Expansive (black cotton) clay was identified to {depth_text}. It swells when "
                "wet and shrinks when dry regardless of the load on it, and it will lift and "
                "drop a foundation seasonally. Either excavate it out under the footprint and "
                "replace with compacted approved fill extending at least 1 m beyond the footing "
                "edge, or found below the zone of seasonal moisture change, or isolate the "
                "structure from it with a void former.",
                True,
                "Expansive material removed or bypassed, proved by trial pit records across "
                "the footprint, and the replacement fill compaction-tested.",
                "Expansive clay identified in the investigation",
            ))
            after.append((
                "Keep water away from the foundation for the life of the building",
                "On expansive ground, drainage is structural. Fall the ground away from the "
                "building, line the perimeter with a paved apron, keep soakaways and septic "
                "tanks well clear, and repair leaking pipes immediately. Most black cotton "
                "damage is caused by water reaching soil that was dry when it was built on.",
                False,
                "Perimeter apron, surface falls and drainage installed and maintained.",
                "Expansive clay identified in the investigation",
            ))
        else:
            before.append((
                "Allow for swelling pressure on the shaft",
                "Expansive clay grips a pile shaft and lifts it when it swells. Sleeve or "
                "debond the shaft through the active zone, and check the pile for the uplift "
                "this generates as well as for compression.",
                True,
                "Active-zone depth established and the debonded length shown on the drawing.",
                "Expansive clay identified in the investigation",
            ))

    if findings.high_water_table:
        dw = findings.groundwater_depth_m
        where = f"at about {dw:.1f} m" if dw is not None else "close to founding level"
        before.append((
            "Plan dewatering and excavation support before digging",
            f"The water table stands {where}. Excavation below it will flood, the sides will "
            "run, and the formation will soften while it waits for concrete. Agree the "
            "dewatering method (sump pumping, wellpoints or cut-off) and the support to the "
            "excavation sides in advance, and check where the discharge water will go.",
            True,
            "Dewatering method agreed, discharge route and any consent in place, standby pump "
            "on site.",
            "High water table recorded in the investigation",
        ))
        after.append((
            "Check flotation of any buried structure",
            "A buried tank, basement or chamber that is empty when the water table is high "
            "will float. Check the empty case against the highest credible groundwater, not "
            "the level observed on the day of the survey, and add weight or anchorage if the "
            "factor of safety is short.",
            True,
            "Flotation factor of safety of at least 1.1 demonstrated for the empty structure "
            "at the highest credible water level.",
            "High water table recorded in the investigation",
        ))

    if findings.aggressive_ground:
        before.append((
            "Specify concrete for the aggressive ground",
            "The ground or groundwater is aggressive to buried concrete and reinforcement. "
            "Determine the ACEC/DS class from the sulphate, chloride and pH results and "
            "specify the concrete accordingly — sulphate-resisting cement, a lower "
            "water-cement ratio, and increased cover. Protect any buried steelwork.",
            True,
            "Concrete class and cover specified from the actual chemical test results, not "
            "from a default.",
            "Aggressive ground chemistry recorded",
        ))

    if findings.collapsible_soil:
        before.append((
            "Test the soil wet, not only dry",
            "Collapsible volcanic ash and pumice stands up perfectly while it is dry and loses "
            "strength suddenly when it wets. Run a soaked oedometer or double-oedometer test "
            "before relying on the dry strength, and compact or pre-wet the formation as the "
            "design requires.",
            True,
            "Collapse potential measured on a soaked sample and allowed for in the design.",
            "Collapsible soil identified",
        ))

    if findings.made_ground_depth_m:
        before.append((
            "Dig through the made ground, do not found on it",
            f"Made ground was logged to about {findings.made_ground_depth_m:.1f} m. Fill of "
            "unknown origin and compaction settles unpredictably and may be contaminated. "
            "Found beneath it, remove and replace it under the footprint, or pile through it.",
            True,
            "Founding level proved to be in natural ground, or the fill fully removed and "
            "replaced with tested engineered fill.",
            "Made ground logged in the investigation",
        ))

    if findings.organic_or_peat:
        before.append((
            "Remove organic material entirely",
            "Peat and organic soil compress under their own weight for decades and rot away "
            "under load. It is removed from beneath a structure, never built on.",
            True,
            "All organic material removed beneath the loaded area and the base proved.",
            "Organic soil or peat logged",
        ))

    if findings.rock_depth_m is not None and findings.rock_depth_m <= 3.0 and shallow:
        before.append((
            "Plan for rock excavation",
            f"Rock was logged at about {findings.rock_depth_m:.1f} m. Excavation below this "
            "level will need breaking or hydraulic splitting rather than a digger bucket - "
            "price and programme it. Where the footing sits partly on rock and partly on "
            "soil, deepen onto rock throughout or separate the two: the differential "
            "settlement across that boundary is what cracks the wall.",
            False,
            "Rock level surveyed across the footprint and the founding level set to avoid a "
            "part-rock, part-soil footing.",
            "Shallow rock logged in the investigation",
        ))

    if findings.seismic_pga_g is not None and findings.seismic_pga_g >= 0.10:
        after.append((
            "Tie the foundations together",
            f"Design ground acceleration of about {findings.seismic_pga_g:.2f} g means the "
            "foundations must act as one. Cast ground beams tying every pad together in both "
            "directions, continue reinforcement through the joints, and avoid founding parts "
            "of the same structure at different levels or on different strata.",
            True,
            "Tie beams shown in both directions and detailed for continuity; no split-level "
            "founding without a movement joint through the whole structure.",
            "Significant seismic hazard at this location",
        ))

    return before, after


def construction_steps(
    foundation_type: str,
    *,
    findings: GroundFindings | None = None,
    sector_id: str | None = None,
) -> list[Step]:
    """The ordered site sequence for a foundation type, adapted to this site."""
    if foundation_type not in FOUNDATION_TYPES:
        raise KeyError(
            f"Unknown foundation type {foundation_type!r}. "
            f"Known: {sorted(FOUNDATION_TYPES)}"
        )
    findings = findings or GroundFindings()
    base = _SEQUENCES.get(foundation_type, _GENERIC_SEQUENCE)
    before, after = _condition_steps(findings, foundation_type)

    steps: list[Step] = []
    order = 0
    for title, detail, hold, verify, trigger in before:
        order += 1
        steps.append(Step(order, title, detail, hold, verify, trigger))
    for title, detail, hold, verify in base:
        order += 1
        steps.append(Step(order, title, detail, hold, verify))
    for title, detail, hold, verify, trigger in after:
        order += 1
        steps.append(Step(order, title, detail, hold, verify, trigger))

    sector = get_sector(sector_id)
    order += 1
    steps.append(Step(
        order,
        "Record what was built, and by whom",
        "Compile the as-built record: founding levels actually reached, the inspection "
        "photographs, concrete cube results, compaction tests and any departure from the "
        f"design. For {sector.label.lower()} this record is what an engineer signs against, "
        "and what anyone investigating a future problem will ask for first.",
        True,
        "As-built foundation record complete and handed over.",
    ))
    return steps


def steps_as_dicts(steps: list[Step]) -> list[dict[str, Any]]:
    return [s.as_dict() for s in steps]
