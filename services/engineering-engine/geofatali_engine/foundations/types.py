"""The foundation systems GeoFatali can screen and describe."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FoundationType:
    id: str
    label: str
    family: str
    summary: str
    suits: tuple[str, ...]
    avoid_when: tuple[str, ...]
    relative_cost: str  # "low" | "moderate" | "high" | "very high"
    buildability: str


FOUNDATION_TYPES: dict[str, FoundationType] = {}


def _add(f: FoundationType) -> FoundationType:
    FOUNDATION_TYPES[f.id] = f
    return f


_add(FoundationType(
    id="strip",
    label="Strip footing",
    family="shallow",
    summary="A continuous footing under a load-bearing wall.",
    suits=("Load-bearing masonry", "Light, evenly distributed wall loads", "Competent ground within 1.5 m"),
    avoid_when=("Column-and-beam frames with concentrated loads", "Soft or highly variable ground"),
    relative_cost="low",
    buildability="Hand-excavatable; no plant beyond a mixer on most sites.",
))
_add(FoundationType(
    id="pad",
    label="Isolated pad footing",
    family="shallow",
    summary="A square or rectangular footing under a single column.",
    suits=("Framed structures on competent ground", "Well-spaced columns", "Low to medium rise"),
    avoid_when=("Pads would overlap", "Settlement governs", "Ground is soft or variable across the footprint"),
    relative_cost="low",
    buildability="Simple, repeatable and the cheapest framed-building foundation.",
))
_add(FoundationType(
    id="combined",
    label="Combined footing",
    family="shallow",
    summary="One footing carrying two or more columns, used where pads would clash or a column sits on a boundary.",
    suits=("Close column spacing", "Boundary or party-wall columns", "Unequal adjacent column loads"),
    avoid_when=("Columns are far apart", "Ground is too weak for any shallow system"),
    relative_cost="moderate",
    buildability="More reinforcement and setting out than a pad, but still a shallow excavation.",
))
_add(FoundationType(
    id="raft",
    label="Raft (mat) foundation",
    family="shallow",
    summary="A single slab under the whole structure, spreading the load and bridging weak patches.",
    suits=("Weak or variable ground", "Pads that would cover more than half the plan area", "Expansive or compressible soils", "Where a stiff foundation is needed to limit differential settlement"),
    avoid_when=("Very deep soft strata where the raft would still settle excessively", "Steeply sloping sites"),
    relative_cost="moderate",
    buildability="More concrete and steel, but one pour and no deep excavation.",
))
_add(FoundationType(
    id="piled_raft",
    label="Piled raft",
    family="hybrid",
    summary="A raft with piles under the heaviest areas, sharing the load between slab and piles.",
    suits=("Tall buildings on mixed ground", "Where a raft alone settles too much", "Controlling differential settlement under core walls"),
    avoid_when=("Simpler systems are adequate", "Ground investigation is too thin to model load sharing"),
    relative_cost="high",
    buildability="Requires piling plant and careful design of the load split.",
))
_add(FoundationType(
    id="bored_pile",
    label="Bored (cast in situ) piles",
    family="deep",
    summary="Piles drilled and concreted in place, carrying load past weak strata to a competent layer.",
    suits=("Deep weak or compressible ground", "High column loads", "Built-up areas where driving noise and vibration are unacceptable", "Founding on deep rock"),
    avoid_when=("Competent bearing stratum is within shallow reach", "No rig access to the site"),
    relative_cost="high",
    buildability="Needs a rig, spoil disposal, and support fluid or casing below the water table.",
))
_add(FoundationType(
    id="driven_pile",
    label="Driven (displacement) piles",
    family="deep",
    summary="Precast or steel piles hammered or vibrated into the ground.",
    suits=("Loose to medium granular soils", "Sites where spoil must be avoided", "Marine and over-water works", "Repetitive light foundations such as solar arrays"),
    avoid_when=("Shallow rock or obstructions cause early refusal", "Vibration would damage neighbouring structures"),
    relative_cost="moderate",
    buildability="Fast and repeatable, and the driving record is itself a test of the ground.",
))
_add(FoundationType(
    id="ground_improvement_shallow",
    label="Ground improvement with a shallow foundation",
    family="improvement",
    summary="Treat the ground — excavate and replace, compact, stabilise or install stone columns — then found shallow on the improved layer.",
    suits=("Shallow weak layer over competent ground", "Expansive clay within reach of excavation", "Loose fill and made ground", "Where piling plant cannot reach the site"),
    avoid_when=("Weak stratum is deep", "Programme cannot absorb a settlement or preload period"),
    relative_cost="moderate",
    buildability="Plant is earthmoving rather than piling, which suits remote and small sites.",
))
_add(FoundationType(
    id="pad_and_chimney",
    label="Pad and chimney (uplift block)",
    family="shallow",
    summary="A buried slab with a concrete shaft to the surface, resisting uplift by the weight of the soil above it.",
    suits=("Lattice tower legs in tension", "Transmission towers", "Telecom masts", "Guy anchors"),
    avoid_when=("The soil frustum above the pad cannot supply the required weight", "The water table submerges the block and halves its effective weight"),
    relative_cost="moderate",
    buildability="Backfill compaction is the design — poorly compacted backfill fails in uplift.",
))
_add(FoundationType(
    id="gravity_base",
    label="Gravity base",
    family="shallow",
    summary="A large mass foundation that resists overturning and sliding by its own weight.",
    suits=("Wind turbines", "Quay walls", "Heavily loaded, moment-governed structures on competent ground"),
    avoid_when=("Ground is compressible, so rotational stiffness cannot be achieved", "Excavation volume is impractical"),
    relative_cost="high",
    buildability="A large single pour; concrete supply and temperature control matter.",
))
_add(FoundationType(
    id="ring_beam",
    label="Ring beam with compacted pad",
    family="shallow",
    summary="A reinforced ring under a tank shell, with an engineered fill pad inside it.",
    suits=("Steel storage tanks", "Silos", "Circular structures with heavy shell loads"),
    avoid_when=("The ground below settles differentially across the tank diameter", "Deep soft clay"),
    relative_cost="moderate",
    buildability="Requires strict compaction control and a settlement survey during hydrotest.",
))
_add(FoundationType(
    id="rock_socket",
    label="Rock-socketed foundation",
    family="deep",
    summary="A shaft drilled and keyed into sound rock, transferring load by socket friction and end bearing.",
    suits=("Shallow or moderately deep sound rock", "High loads and high uplift", "Bridge piers on rock"),
    avoid_when=("Rock is deeply weathered or heavily jointed", "Coring data and RQD are not available"),
    relative_cost="high",
    buildability="Needs rock drilling and core evidence that the socket is in sound rock.",
))
_add(FoundationType(
    id="ground_screw",
    label="Ground screw / helical pile",
    family="deep",
    summary="A helical steel shaft screwed into the ground, taking compression and uplift immediately.",
    suits=("Solar arrays", "Light structures", "Temporary and reversible works", "Sites where concrete is impractical"),
    avoid_when=("Dense gravel or rock prevents installation", "Ground is aggressive to galvanised steel"),
    relative_cost="low",
    buildability="Installed torque is a direct, recorded measure of capacity, one pile at a time.",
))
_add(FoundationType(
    id="subgrade_improvement",
    label="Subgrade improvement (pavement formation)",
    family="improvement",
    summary="Strengthen the formation by replacement, stabilisation with lime or cement, or a capping layer.",
    suits=("Roads, runways and hardstanding on weak subgrade", "Expansive or dispersive subgrade soils"),
    avoid_when=("Subgrade already meets the required CBR", "Material for capping is not locally available"),
    relative_cost="low",
    buildability="Ordinary earthworks plant; lime stabilisation needs a mixer and moisture control.",
))
_add(FoundationType(
    id="caisson",
    label="Caisson / well foundation",
    family="deep",
    summary="A large sunk shaft founded well below scour level, common for bridge piers in rivers.",
    suits=("Bridge piers in rivers", "Deep scour", "Heavy concentrated loads over water"),
    avoid_when=("Shallow rock makes sinking impractical", "Piling would be cheaper and faster"),
    relative_cost="very high",
    buildability="Specialist work; sinking control and tilt correction dominate the programme.",
))
_add(FoundationType(
    id="cut_off_and_foundation_treatment",
    label="Cut-off and foundation treatment",
    family="improvement",
    summary="Grout curtain, slurry cut-off wall or blanket treatment to control seepage under an embankment.",
    suits=("Earth dams", "Flood embankments", "Water retention on permeable foundations"),
    avoid_when=("The foundation is already impermeable", "Permeability testing has not been done"),
    relative_cost="high",
    buildability="Specialist grouting or trenching; verification is by water testing, not inspection.",
))
_add(FoundationType(
    id="lined_excavation",
    label="Lined excavation / engineered liner",
    family="improvement",
    summary="A compacted clay or geomembrane liner to hold water in, or keep contamination in.",
    suits=("Water pans and reservoirs", "Landfill cells", "Effluent lagoons"),
    avoid_when=("Suitable clay is not available and geomembrane is unaffordable"),
    relative_cost="moderate",
    buildability="Compaction moisture control and seam testing are the whole job.",
))
_add(FoundationType(
    id="anchored_wall",
    label="Anchored or propped retaining wall",
    family="retaining",
    summary="An embedded wall held by ground anchors or props rather than by its own weight.",
    suits=("Deep basements", "Restricted sites", "Tall retained heights"),
    avoid_when=("Anchors would cross a neighbouring boundary without a wayleave", "Ground is too weak to develop anchor capacity"),
    relative_cost="high",
    buildability="Anchors must be proof-tested; wall movement must be monitored during excavation.",
))
_add(FoundationType(
    id="thrust_block",
    label="Thrust block",
    family="shallow",
    summary="A mass concrete block resisting the out-of-balance force at a pipeline bend or valve.",
    suits=("Pressurised pipelines", "Bends, tees and closed ends"),
    avoid_when=("The soil behind the block cannot mobilise passive resistance"),
    relative_cost="low",
    buildability="Simple, but must bear against undisturbed ground, never against backfill.",
))
_add(FoundationType(
    id="bedding_and_surround",
    label="Pipe bedding and surround",
    family="shallow",
    summary="Graded granular bedding that supports a buried pipe uniformly along its length.",
    suits=("Buried pipelines and ducts", "Trench construction in any ground"),
    avoid_when=("The trench cannot be kept dry and stable"),
    relative_cost="low",
    buildability="Bedding class is chosen to match the pipe strength and the trench depth.",
))
_add(FoundationType(
    id="ballast_block",
    label="Ballast block",
    family="shallow",
    summary="Precast or in-situ blocks that hold a light structure down by weight alone.",
    suits=("Solar tables where piling is impossible", "Rooftop plant", "Temporary structures"),
    avoid_when=("Uplift exceeds what weight can economically resist"),
    relative_cost="low",
    buildability="No excavation; the ground only has to carry a modest bearing pressure.",
))
_add(FoundationType(
    id="rock_anchor",
    label="Rock anchor",
    family="deep",
    summary="Steel tendons grouted into rock to hold a structure down against uplift.",
    suits=("Masts and towers on rock", "Dams", "Uplift-governed foundations on shallow rock"),
    avoid_when=("Rock is weathered or the groundwater is aggressive to the tendon"),
    relative_cost="high",
    buildability="Every anchor is proof-tested; corrosion protection is a design item, not a detail.",
))
