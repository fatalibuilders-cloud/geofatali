"""Sectors — every industry that stands on the ground.

A geotechnical investigation is not a building activity. The same borehole,
the same SPT rig and the same laboratory serve a road, a dam, a wind turbine,
a transmission tower, a pipeline and a landfill — but what the ground has to
be *good at* changes completely between them.

A house cares about bearing pressure and differential settlement.
A road cares about CBR, subgrade class and swell, and barely about bearing.
A dam cares about seepage, piping and slope stability, and a bearing failure
is the least of its problems.
A wind turbine cares about rotational stiffness and millions of load cycles.
A transmission tower cares about uplift, because half its legs are in tension.

So the sector a project belongs to is a first-class input in GeoFatali. It
selects which checks are run, which foundation families are even candidates,
which settlement limit applies, and what the investigation has to include
before the answer means anything. Everything downstream reads this table.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    id: str
    label: str
    why: str


#: The full vocabulary of geotechnical limit states the engine knows about.
CHECKS: dict[str, Check] = {
    "bearing": Check("bearing", "Bearing capacity", "The ground must not shear under the load."),
    "settlement": Check("settlement", "Total settlement", "The structure must not sink more than it can tolerate."),
    "differential_settlement": Check("differential_settlement", "Differential settlement", "Uneven movement cracks structures long before uniform movement does."),
    "sliding": Check("sliding", "Sliding", "Horizontal load must not push the foundation sideways."),
    "overturning": Check("overturning", "Overturning", "Moment must not tip the foundation over its edge."),
    "uplift": Check("uplift", "Uplift and pull-out", "Tension in the foundation must be resisted by weight or anchorage."),
    "liquefaction": Check("liquefaction", "Liquefaction", "Saturated loose sand can lose all strength in an earthquake."),
    "slope_stability": Check("slope_stability", "Slope stability", "The ground mass itself must not slide."),
    "scour": Check("scour", "Scour", "Moving water removes the soil the foundation stands on."),
    "frost_heave": Check("frost_heave", "Frost heave", "Freezing ground expands and lifts shallow foundations."),
    "swell": Check("swell", "Shrink-swell", "Expansive clay moves seasonally whatever the load is."),
    "collapse": Check("collapse", "Collapse settlement", "Open-structured soils lose strength suddenly on wetting."),
    "dynamic": Check("dynamic", "Dynamic and cyclic loading", "Repeated load degrades soil stiffness and strength."),
    "seepage": Check("seepage", "Seepage and piping", "Water flowing through the ground erodes it from within."),
    "buoyancy": Check("buoyancy", "Buoyancy / flotation", "An empty buried structure floats when the water table rises."),
    "corrosion": Check("corrosion", "Ground aggressivity", "Sulphates and chlorides attack buried concrete and steel."),
    "thermal": Check("thermal", "Thermal resistivity", "Buried cables and pipes need the ground to carry heat away."),
    "subgrade": Check("subgrade", "Subgrade strength (CBR)", "Pavement thickness is designed from the subgrade's CBR."),
    "stiffness": Check("stiffness", "Rotational stiffness", "Tall slender structures are governed by how much the base rotates."),
}


@dataclass(frozen=True)
class Sector:
    id: str
    label: str
    summary: str
    typical_structures: tuple[str, ...]
    #: Which limit states must be checked before an answer means anything.
    governing_checks: tuple[str, ...]
    #: Minimum factor of safety on net ultimate bearing under working load.
    default_bearing_fs: float
    #: Tolerable total settlement, mm. A road tolerates far more than a bridge.
    settlement_limit_mm: float
    angular_distortion_limit: float
    #: Foundation families worth screening for this sector.
    candidate_foundations: tuple[str, ...]
    #: What an adequate investigation has to include here.
    required_investigation: tuple[str, ...]
    standards: tuple[str, ...]
    note: str = ""


SECTORS: dict[str, Sector] = {}


def _add(sector: Sector) -> Sector:
    SECTORS[sector.id] = sector
    return sector


BUILDINGS_LOW_RISE = _add(Sector(
    id="buildings_low_rise",
    label="Buildings — low rise (1 to 4 storeys)",
    summary="Houses, maisonettes, small apartment blocks, shops and clinics.",
    typical_structures=("Bungalow", "Maisonette", "Apartment block", "Shop", "Clinic", "School block"),
    governing_checks=("bearing", "settlement", "differential_settlement", "swell", "corrosion"),
    default_bearing_fs=3.0,
    settlement_limit_mm=50.0,
    angular_distortion_limit=1 / 500,
    candidate_foundations=("strip", "pad", "raft", "ground_improvement_shallow"),
    required_investigation=(
        "At least one trial pit or borehole per 300 m2 of footprint, minimum two",
        "Depth at least 1.5 times the footing width below founding level",
        "Atterberg limits wherever clay is logged — the swell check depends on them",
        "Groundwater observation over a wet and a dry season where possible",
    ),
    standards=("EN 1997-1", "BS 8004", "Kenya NBC 2024"),
    note="The commonest failure here is not a bearing failure. It is a shrink-swell "
         "movement in expansive clay that no bearing calculation would have caught.",
))

BUILDINGS_HIGH_RISE = _add(Sector(
    id="buildings_high_rise",
    label="Buildings — medium and high rise (5 storeys and above)",
    summary="Apartment towers, office blocks, hotels and hospitals with basements.",
    typical_structures=("Apartment tower", "Office block", "Hotel", "Hospital", "Mixed-use tower"),
    governing_checks=("bearing", "settlement", "differential_settlement", "liquefaction", "buoyancy", "corrosion"),
    default_bearing_fs=3.0,
    settlement_limit_mm=40.0,
    angular_distortion_limit=1 / 500,
    candidate_foundations=("raft", "piled_raft", "bored_pile", "pad", "ground_improvement_shallow"),
    required_investigation=(
        "Boreholes to at least 1.5 times the raft width, or 5 diameters below pile toe level",
        "SPT at 1.5 m intervals, with undisturbed samples in every cohesive stratum",
        "Oedometer tests on each compressible layer — settlement, not bearing, governs",
        "Groundwater standpipes for the basement design and the flotation check",
        "Sulphate and chloride content of soil and groundwater for the buried concrete spec",
    ),
    standards=("EN 1997-1", "EN 1998-5 (seismic)", "BS 8004", "BS 8102 (below-ground waterproofing)"),
))

INDUSTRIAL = _add(Sector(
    id="industrial",
    label="Industrial buildings and hardstanding",
    summary="Warehouses, factories, godowns and the floor slabs and yards around them.",
    typical_structures=("Warehouse", "Factory", "Godown", "Workshop", "Container yard"),
    governing_checks=("bearing", "settlement", "differential_settlement", "subgrade", "swell"),
    default_bearing_fs=3.0,
    settlement_limit_mm=50.0,
    angular_distortion_limit=1 / 500,
    candidate_foundations=("pad", "strip", "raft", "ground_improvement_shallow", "bored_pile"),
    required_investigation=(
        "Investigation across the full slab footprint, not only under the columns",
        "CBR or plate-load testing of the subgrade for the floor slab",
        "Fill history — industrial sites are commonly built on made ground",
    ),
    note="The frame is light and the floor slab is heavy. A racked warehouse floor at "
         "50 kN/m2 loads the ground harder than the columns do, and it is the slab that "
         "cracks when the ground settles.",
    standards=("EN 1997-1", "TR 34 (concrete industrial floors)"),
))

ROADS = _add(Sector(
    id="roads",
    label="Roads and highways",
    summary="Pavement subgrade, embankments, cuttings and road structures.",
    typical_structures=("Flexible pavement", "Rigid pavement", "Embankment", "Cutting", "Culvert"),
    governing_checks=("subgrade", "swell", "settlement", "slope_stability", "seepage"),
    default_bearing_fs=2.5,
    settlement_limit_mm=100.0,
    angular_distortion_limit=1 / 200,
    candidate_foundations=("subgrade_improvement", "ground_improvement_shallow", "strip", "pad"),
    required_investigation=(
        "DCP or CBR testing at regular chainage along the alignment",
        "Trial pits to at least 1.0 m below formation level",
        "Atterberg limits and swell testing where expansive subgrade is suspected",
        "Borrow-pit investigation for fill and sub-base material",
    ),
    standards=("TRL ORN 31", "TRL ORN 18 (DCP)", "AASHTO M 145", "Kenya Road Design Manual"),
    note="Here the governing number is CBR, not bearing capacity. A subgrade at CBR 2 and "
         "one at CBR 15 differ by hundreds of millimetres of pavement.",
))

RAILWAYS = _add(Sector(
    id="railways",
    label="Railways",
    summary="Track formation, embankments, cuttings and rail structures.",
    typical_structures=("Track formation", "Embankment", "Cutting", "Level crossing"),
    governing_checks=("subgrade", "settlement", "differential_settlement", "dynamic", "slope_stability"),
    default_bearing_fs=3.0,
    settlement_limit_mm=25.0,
    angular_distortion_limit=1 / 1000,
    candidate_foundations=("subgrade_improvement", "ground_improvement_shallow", "bored_pile"),
    required_investigation=(
        "Continuous profiling along the alignment — a soft spot every 200 m is a speed restriction",
        "Cyclic triaxial testing where soft cohesive subgrade is present",
        "Groundwater profile along the whole alignment",
    ),
    standards=("EN 1997-1", "UIC 719R"),
    note="Rail tolerates very little differential movement and loads the formation millions "
         "of times. Cyclic degradation of a soft subgrade, not a single bearing failure, is "
         "what ends up as a track fault.",
))

AIRPORTS = _add(Sector(
    id="airports",
    label="Airports — runways, taxiways and aprons",
    summary="Very large paved areas under concentrated, repeated wheel loads.",
    typical_structures=("Runway", "Taxiway", "Apron", "Hangar"),
    governing_checks=("subgrade", "settlement", "differential_settlement", "dynamic", "swell"),
    default_bearing_fs=3.0,
    settlement_limit_mm=25.0,
    angular_distortion_limit=1 / 1000,
    candidate_foundations=("subgrade_improvement", "ground_improvement_shallow", "raft"),
    required_investigation=(
        "CBR or plate bearing tests on a grid across the whole paved area",
        "Deep investigation under any structure, and shallow investigation everywhere else",
    ),
    standards=("FAA AC 150/5320-6", "ICAO Annex 14"),
))

BRIDGES = _add(Sector(
    id="bridges",
    label="Bridges and culverts",
    summary="Abutments, piers and the ground under and around them.",
    typical_structures=("Bridge abutment", "Bridge pier", "Box culvert", "Footbridge"),
    governing_checks=("bearing", "settlement", "differential_settlement", "scour", "sliding", "slope_stability", "liquefaction"),
    default_bearing_fs=3.0,
    settlement_limit_mm=25.0,
    angular_distortion_limit=1 / 250,
    candidate_foundations=("bored_pile", "caisson", "pad", "raft", "rock_socket"),
    required_investigation=(
        "One borehole minimum at every substructure location — never interpolate across a river",
        "Scour assessment from the hydrology, not from the soil alone",
        "Rock coring with RQD where founding on rock is proposed",
        "Seismic site classification where the region requires it",
    ),
    standards=("EN 1997-1", "AASHTO LRFD section 10", "BS 5400"),
    note="Scour removes the ground a bridge stands on while the bearing calculation stays "
         "perfectly valid. It is the leading cause of bridge foundation failure worldwide.",
))

DAMS = _add(Sector(
    id="dams",
    label="Dams, embankments and water retention",
    summary="Earth and rockfill dams, flood embankments and reservoir basins.",
    typical_structures=("Earth dam", "Rockfill dam", "Flood embankment", "Reservoir basin", "Water pan"),
    governing_checks=("seepage", "slope_stability", "settlement", "bearing", "liquefaction"),
    default_bearing_fs=3.0,
    settlement_limit_mm=200.0,
    angular_distortion_limit=1 / 100,
    candidate_foundations=("cut_off_and_foundation_treatment", "ground_improvement_shallow", "bored_pile"),
    required_investigation=(
        "Permeability testing — falling head, packer or pumping tests through the foundation",
        "Continuous profiling of the full dam footprint and both abutments",
        "Shear strength for rapid-drawdown and end-of-construction stability cases",
        "Borrow investigation for the fill, with compaction and dispersivity testing",
    ),
    standards=("ICOLD bulletins", "EN 1997-1", "USBR Design of Small Dams"),
    note="Dams fail by piping and internal erosion far more often than by bearing failure. "
         "The controlling data is permeability and gradation, not bearing capacity.",
))

WATER_RETAINING = _add(Sector(
    id="water_retaining",
    label="Water and wastewater structures",
    summary="Reservoirs, treatment tanks, pump stations and buried chambers.",
    typical_structures=("Service reservoir", "Treatment tank", "Pump station", "Septic/sewer chamber"),
    governing_checks=("bearing", "settlement", "differential_settlement", "buoyancy", "corrosion", "seepage"),
    default_bearing_fs=3.0,
    settlement_limit_mm=25.0,
    angular_distortion_limit=1 / 1000,
    candidate_foundations=("raft", "bored_pile", "pad", "ground_improvement_shallow"),
    required_investigation=(
        "Groundwater levels through a seasonal cycle — the flotation check needs the highest, not the observed",
        "Sulphate, chloride and pH of soil and groundwater",
        "Differential settlement assessment across the full tank footprint",
    ),
    standards=("EN 1992-3", "BS 8007", "EN 1997-1"),
    note="An empty tank in a high water table floats. The flotation check is done on an "
         "empty structure and the highest credible groundwater, not on the level measured "
         "on the day of the survey.",
))

RETAINING = _add(Sector(
    id="retaining",
    label="Retaining structures and excavations",
    summary="Retaining walls, basement walls, sheet piling and temporary works.",
    typical_structures=("Gravity retaining wall", "Cantilever wall", "Basement wall", "Sheet pile wall", "Gabion wall"),
    governing_checks=("sliding", "overturning", "bearing", "slope_stability", "seepage", "settlement"),
    default_bearing_fs=3.0,
    settlement_limit_mm=25.0,
    angular_distortion_limit=1 / 500,
    candidate_foundations=("strip", "pad", "bored_pile", "anchored_wall"),
    required_investigation=(
        "Shear strength of both the retained soil and the founding soil",
        "Groundwater behind the wall — drainage is the design, and the usual omission",
        "Survey of adjacent structures within the zone of influence",
    ),
    standards=("EN 1997-1 section 9", "BS 8002", "CIRIA C760"),
    note="Most retaining wall failures are drainage failures. Water pressure behind an "
         "undrained wall can exceed the soil pressure it was designed for.",
))

TELECOM = _add(Sector(
    id="telecom",
    label="Telecommunication masts and towers",
    summary="Guyed masts, self-supporting lattice towers and rooftop structures.",
    typical_structures=("Guyed mast", "Lattice tower", "Monopole", "Rooftop mast"),
    governing_checks=("uplift", "overturning", "bearing", "stiffness", "corrosion"),
    default_bearing_fs=3.0,
    settlement_limit_mm=25.0,
    angular_distortion_limit=1 / 1000,
    candidate_foundations=("pad_and_chimney", "bored_pile", "raft", "rock_anchor"),
    required_investigation=(
        "Investigation to at least 1.5 times the proposed block depth at each leg and anchor",
        "Uplift assessment — the frustum of soil resisting pull-out, and its unit weight",
        "Ground aggressivity for the buried steel and the earthing design",
        "Resistivity for the earthing system, which shares this investigation",
    ),
    standards=("EN 1993-3-1", "TIA-222", "EN 1997-1"),
    note="A mast foundation is usually governed by uplift and overturning, not bearing. "
         "Three legs of a lattice tower push down; the fourth pulls out.",
))

POWER_TRANSMISSION = _add(Sector(
    id="power_transmission",
    label="Power transmission and distribution",
    summary="Transmission tower footings, substation structures and pole foundations.",
    typical_structures=("Lattice transmission tower", "Substation gantry", "Transformer plinth", "Pole"),
    governing_checks=("uplift", "overturning", "bearing", "corrosion", "thermal"),
    default_bearing_fs=3.0,
    settlement_limit_mm=25.0,
    angular_distortion_limit=1 / 500,
    candidate_foundations=("pad_and_chimney", "bored_pile", "rock_anchor", "pad"),
    required_investigation=(
        "One investigation point per tower along the line — ground changes between pylons",
        "Soil resistivity for earthing and for buried-cable ampacity",
        "Uplift capacity assessment at every tension leg",
    ),
    standards=("EN 50341", "IEEE 691", "EN 1997-1"),
))

WIND = _add(Sector(
    id="wind_energy",
    label="Wind energy",
    summary="Wind turbine gravity bases and piled foundations.",
    typical_structures=("Onshore turbine gravity base", "Piled turbine base", "Met mast"),
    governing_checks=("stiffness", "overturning", "bearing", "dynamic", "settlement", "uplift"),
    default_bearing_fs=3.0,
    settlement_limit_mm=25.0,
    angular_distortion_limit=1 / 1000,
    candidate_foundations=("gravity_base", "bored_pile", "rock_anchor"),
    required_investigation=(
        "Borehole and geophysics at every turbine position",
        "Small-strain shear modulus G0, by seismic CPT or cross-hole — rotational stiffness is a serviceability criterion with a hard limit",
        "Cyclic degradation testing for the fatigue load cases",
        "Groundwater and its seasonal range",
    ),
    standards=("IEC 61400-6", "DNV-ST-0126", "EN 1997-1"),
    note="A turbine foundation is designed for rotational stiffness and twenty years of "
         "load cycles. Bearing capacity is rarely what sizes it.",
))

SOLAR = _add(Sector(
    id="solar_energy",
    label="Solar energy",
    summary="Ground-mounted PV pile and screw foundations, and inverter/substation pads.",
    typical_structures=("Driven pile table", "Ground screw", "Concrete ballast block", "Inverter station"),
    governing_checks=("uplift", "bearing", "corrosion", "swell", "settlement"),
    default_bearing_fs=2.5,
    settlement_limit_mm=50.0,
    angular_distortion_limit=1 / 200,
    candidate_foundations=("driven_pile", "ground_screw", "ballast_block", "pad"),
    required_investigation=(
        "Pile driveability assessment across the array — refusal on shallow rock is the usual surprise",
        "Pull-out tests on trial piles before the main drive",
        "Soil resistivity and aggressivity for galvanised steel in contact with the ground",
    ),
    standards=("EN 1997-1", "SEAOC PV2"),
    note="A solar array is thousands of small, lightly loaded, uplift-governed foundations. "
         "The investigation has to cover area, not depth.",
))

PIPELINES = _add(Sector(
    id="pipelines",
    label="Pipelines and buried services",
    summary="Water, sewer, oil, gas and cable routes and their trenches.",
    typical_structures=("Buried pipeline", "Trenchless crossing", "Thrust block", "Cable duct"),
    governing_checks=("settlement", "buoyancy", "corrosion", "thermal", "slope_stability", "seepage"),
    default_bearing_fs=2.5,
    settlement_limit_mm=50.0,
    angular_distortion_limit=1 / 500,
    candidate_foundations=("bedding_and_surround", "bored_pile", "thrust_block", "ground_improvement_shallow"),
    required_investigation=(
        "Trial pits along the route at regular intervals and at every crossing",
        "Groundwater and trench-stability assessment for the excavation itself",
        "Soil aggressivity and resistivity for the coating and cathodic protection design",
        "Thermal resistivity where buried cables must shed heat",
    ),
    standards=("EN 1594", "ASME B31", "EN 1997-1"),
))

TANKS = _add(Sector(
    id="storage_tanks",
    label="Storage tanks and silos",
    summary="Steel storage tanks, silos and bulk storage on ring or raft foundations.",
    typical_structures=("Steel storage tank", "Concrete silo", "Grain store", "Fuel tank"),
    governing_checks=("settlement", "differential_settlement", "bearing", "liquefaction", "buoyancy"),
    default_bearing_fs=3.0,
    settlement_limit_mm=100.0,
    angular_distortion_limit=1 / 500,
    candidate_foundations=("ring_beam", "raft", "bored_pile", "ground_improvement_shallow"),
    required_investigation=(
        "Investigation to at least one tank diameter below founding level — a tank stresses the ground very deep",
        "Oedometer testing through the full compressible profile",
        "Provision for a hydrotest settlement survey before commissioning",
    ),
    standards=("API 650 Appendix B", "EN 14015", "EN 1997-1"),
    note="A flat-bottomed tank is a uniform load over a huge area, so the stress reaches far "
         "deeper than under a building. Edge-to-centre differential settlement, not bearing, "
         "is what tears the shell.",
))

MARINE = _add(Sector(
    id="marine",
    label="Ports, marine and coastal works",
    summary="Quay walls, jetties, breakwaters and reclaimed land.",
    typical_structures=("Quay wall", "Jetty", "Breakwater", "Reclamation", "Slipway"),
    governing_checks=("bearing", "sliding", "scour", "settlement", "liquefaction", "corrosion", "slope_stability"),
    default_bearing_fs=3.0,
    settlement_limit_mm=50.0,
    angular_distortion_limit=1 / 300,
    candidate_foundations=("bored_pile", "driven_pile", "caisson", "gravity_base", "ground_improvement_shallow"),
    required_investigation=(
        "Over-water boreholes at each structure line, with tidal correction of levels",
        "Chloride and sulphate profile for durability of everything buried or submerged",
        "Liquefaction assessment of hydraulic fill",
        "Scour and wave/current data alongside the ground data",
    ),
    standards=("BS 6349", "EN 1997-1", "PIANC guidance"),
))

MINING = _add(Sector(
    id="mining",
    label="Mining, quarrying and tailings",
    summary="Pit slopes, waste dumps, tailings dams, haul roads and plant foundations.",
    typical_structures=("Open pit slope", "Waste rock dump", "Tailings storage facility", "Crusher foundation", "Haul road"),
    governing_checks=("slope_stability", "seepage", "settlement", "bearing", "dynamic", "liquefaction"),
    default_bearing_fs=3.0,
    settlement_limit_mm=50.0,
    angular_distortion_limit=1 / 300,
    candidate_foundations=("raft", "bored_pile", "pad", "ground_improvement_shallow", "rock_socket"),
    required_investigation=(
        "Rock mass characterisation with RQD, joint sets and discontinuity orientation",
        "Tailings characterisation for static liquefaction — this is the failure mode that kills people",
        "Groundwater and depressurisation assessment for pit slopes",
        "Dynamic soil properties under crushers and mills",
    ),
    standards=("GISTM (tailings)", "EN 1997-1", "ISRM suggested methods"),
    note="Tailings dam failures are the deadliest geotechnical events on record. Static "
         "liquefaction of loose, saturated tailings is the mechanism, and it is a laboratory "
         "and monitoring question, not a bearing-capacity one.",
))

AGRICULTURE = _add(Sector(
    id="agriculture",
    label="Agriculture and irrigation",
    summary="Water pans, irrigation canals, greenhouses, stores and farm structures.",
    typical_structures=("Water pan", "Irrigation canal", "Greenhouse", "Grain store", "Livestock shed"),
    governing_checks=("seepage", "swell", "bearing", "settlement", "slope_stability"),
    default_bearing_fs=2.5,
    settlement_limit_mm=75.0,
    angular_distortion_limit=1 / 300,
    candidate_foundations=("strip", "pad", "ground_improvement_shallow", "lined_excavation"),
    required_investigation=(
        "Permeability of the pan or canal base — a water pan in permeable ground does not hold water",
        "Dispersivity testing where the soil is sodic, since dispersive clay tunnels and collapses",
        "Simple trial pits are usually sufficient for the structures themselves",
    ),
    standards=("FAO irrigation guidelines", "EN 1997-1"),
))

WASTE = _add(Sector(
    id="waste",
    label="Landfill and contaminated land",
    summary="Waste cells, liners, capping and development over former tips.",
    typical_structures=("Landfill cell", "Clay or geomembrane liner", "Capping layer", "Development over made ground"),
    governing_checks=("seepage", "settlement", "slope_stability", "bearing", "corrosion"),
    default_bearing_fs=3.0,
    settlement_limit_mm=300.0,
    angular_distortion_limit=1 / 100,
    candidate_foundations=("bored_pile", "ground_improvement_shallow", "raft", "lined_excavation"),
    required_investigation=(
        "Permeability of the liner material and the natural ground beneath it",
        "Gas and leachate monitoring — this is a health and safety matter before it is a design one",
        "Thickness, age and composition of the waste where building over it",
        "Chemical testing for the aggressivity of the ground to concrete and to people",
    ),
    standards=("EN 1997-1", "Landfill Directive 1999/31/EC", "BS 10175 (contaminated land)"),
    note="Waste settles for decades under its own weight. Nothing is founded on it without "
         "either piling through it or accepting movement measured in hundreds of millimetres.",
))

DEFAULT_SECTOR_ID = "buildings_low_rise"


def get_sector(sector_id: str | None) -> Sector:
    if sector_id is None:
        return SECTORS[DEFAULT_SECTOR_ID]
    try:
        return SECTORS[sector_id]
    except KeyError as exc:
        raise KeyError(
            f"Unknown sector {sector_id!r}. Known sectors: {sorted(SECTORS)}"
        ) from exc


def checks_for(sector_id: str | None) -> tuple[Check, ...]:
    return tuple(CHECKS[c] for c in get_sector(sector_id).governing_checks)
