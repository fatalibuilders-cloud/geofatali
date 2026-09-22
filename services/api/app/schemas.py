"""Request and response models for the calculation API.

These are the wire contract. They deliberately mirror the engine's own
dataclasses rather than flattening them, so that a stored request can be
replayed against the engine years later and produce the same numbers.

Every field carries its unit in its name. The API never accepts a bare
quantity whose unit has to be guessed.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Method = Literal["terzaghi", "meyerhof", "hansen", "vesic"]
Shape = Literal["strip", "square", "rectangular", "circular"]
Analysis = Literal["drained", "undrained"]
SourceName = Literal[
    "LABORATORY", "FIELD", "ENGINEER", "IMPORTED", "USER", "AI", "ESTIMATED"
]


class SoilIn(BaseModel):
    unit_weight_kn_m3: float = Field(gt=0, le=30)
    cohesion_kpa: float | None = Field(default=None, ge=0)
    friction_angle_deg: float | None = Field(default=None, ge=0, lt=60)
    saturated_unit_weight_kn_m3: float | None = Field(default=None, gt=0, le=30)
    analysis: Analysis = "drained"
    cohesion_source: SourceName = "USER"
    friction_source: SourceName = "USER"
    unit_weight_source: SourceName = "USER"
    reference: str | None = None


class FootingIn(BaseModel):
    width_m: float = Field(gt=0, le=50)
    depth_m: float = Field(ge=0, le=30)
    length_m: float | None = Field(default=None, gt=0, le=200)
    shape: Shape = "rectangular"


class GroundIn(BaseModel):
    groundwater_depth_m: float | None = Field(default=None, ge=0)
    ground_slope_deg: float = Field(default=0.0, ge=0, lt=45)
    base_tilt_deg: float = Field(default=0.0, ge=0, lt=45)
    load_inclination_deg: float = Field(default=0.0, ge=0, lt=90)
    groundwater_observed: bool = False


class BearingCapacityRequest(BaseModel):
    soil: SoilIn
    foundation: FootingIn
    groundwater: GroundIn = GroundIn()
    method: Method = "vesic"
    safety_factor: float | None = Field(default=None, gt=0, le=10)
    standard: str | None = None


class FootingSizingRequest(BaseModel):
    service_load_kn: float = Field(gt=0)
    soil: SoilIn
    depth_m: float = Field(gt=0, le=30)
    shape: Shape = "square"
    length_over_width: float = Field(default=1.0, ge=1.0, le=10.0)
    groundwater: GroundIn = GroundIn()
    method: Method = "vesic"
    safety_factor: float | None = Field(default=None, gt=0, le=10)
    standard: str | None = None
    max_width_m: float = Field(default=6.0, gt=0, le=30)


class ElasticSettlementRequest(BaseModel):
    applied_pressure_kpa: float = Field(gt=0)
    width_m: float = Field(gt=0)
    length_m: float | None = Field(default=None, gt=0)
    depth_m: float = Field(default=0.0, ge=0)
    youngs_modulus_kpa: float | None = Field(default=None, gt=0)
    poissons_ratio: float = Field(default=0.3, ge=0, lt=0.5)
    rigid: bool = True
    modulus_source: SourceName = "USER"
    standard: str | None = None


class ConsolidationRequest(BaseModel):
    layer_thickness_m: float = Field(gt=0)
    layer_mid_depth_m: float = Field(gt=0)
    initial_void_ratio: float | None = Field(default=None, gt=0)
    compression_index_cc: float | None = Field(default=None, gt=0)
    recompression_index_cr: float | None = Field(default=None, gt=0)
    preconsolidation_pressure_kpa: float | None = Field(default=None, gt=0)
    unit_weight_kn_m3: float = Field(gt=0)
    groundwater_depth_m: float | None = Field(default=None, ge=0)
    stress_increment_kpa: float | None = Field(default=None, gt=0)
    load_kn: float | None = Field(default=None, gt=0)
    footing_width_m: float | None = Field(default=None, gt=0)
    footing_length_m: float | None = Field(default=None, gt=0)
    footing_depth_m: float = Field(default=0.0, ge=0)
    stress_method: Literal["stress_2to1", "boussinesq_rectangle"] = "stress_2to1"
    standard: str | None = None


class ColumnLoadRequest(BaseModel):
    tributary_width_m: float = Field(gt=0, le=30)
    tributary_length_m: float = Field(gt=0, le=30)
    floors: int = Field(ge=1, le=60)
    floor_height_m: float = Field(default=3.0, ge=2.0, le=8.0)
    occupancy: str = "residential"
    roof_type: str = "iron_sheets"
    wall_type: str = "none"
    wall_length_m: float = Field(default=0.0, ge=0)
    column_size_m: float = Field(default=0.3, gt=0, le=3.0)
    slab_thickness_mm: float | None = Field(default=None, ge=100, le=600)
    standard: str | None = None


class FindingsIn(BaseModel):
    expansive_clay: bool = False
    swell_potential: Literal["UNKNOWN", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"] = "UNKNOWN"
    high_water_table: bool = False
    groundwater_depth_m: float | None = Field(default=None, ge=0)
    aggressive_ground: bool = False
    collapsible_soil: bool = False
    soft_layer_depth_m: float | None = Field(default=None, ge=0)
    rock_depth_m: float | None = Field(default=None, ge=0)
    made_ground_depth_m: float | None = Field(default=None, ge=0)
    organic_or_peat: bool = False
    seismic_pga_g: float | None = Field(default=None, ge=0, le=2.0)
    black_cotton_depth_m: float | None = Field(default=None, ge=0)


class FoundationScreeningRequest(BaseModel):
    sector: str = "buildings_low_rise"
    service_load_kn: float | None = Field(default=None, gt=0)
    net_allowable_kpa: float | None = Field(default=None, gt=0)
    required_footing_width_m: float | None = Field(default=None, gt=0)
    utilisation: float | None = Field(default=None, ge=0)
    total_settlement_mm: float | None = Field(default=None, ge=0)
    column_spacing_m: float | None = Field(default=None, gt=0)
    footprint_area_m2: float | None = Field(default=None, gt=0)
    number_of_columns: int | None = Field(default=None, ge=1)
    floors: int = Field(default=1, ge=1)
    competent_stratum_depth_m: float | None = Field(default=None, ge=0)
    trial_founding_depth_m: float = Field(default=1.5, gt=0)
    uplift_kn: float | None = Field(default=None, ge=0)
    findings: FindingsIn = FindingsIn()
    standard: str | None = None


class SptCorrectionRequest(BaseModel):
    n_raw: int = Field(ge=0, le=200)
    energy_ratio_percent: float = Field(default=60.0, gt=0, le=100)
    borehole_diameter_mm: float = Field(default=100.0, gt=0, le=1000)
    rod_length_m: float = Field(default=6.0, gt=0, le=100)
    liner_absent_in_lined_sampler: bool = False
    effective_overburden_kpa: float | None = Field(default=None, gt=0)


class DcpRequest(BaseModel):
    blows: int = Field(gt=0)
    penetration_mm: float = Field(gt=0)


class ClassificationRequest(BaseModel):
    fines_percent: float | None = Field(default=None, ge=0, le=100)
    gravel_percent: float | None = Field(default=None, ge=0, le=100)
    sand_percent: float | None = Field(default=None, ge=0, le=100)
    liquid_limit: float | None = Field(default=None, ge=0, le=200)
    plastic_limit: float | None = Field(default=None, ge=0, le=200)
    cu: float | None = Field(default=None, gt=0)
    cc: float | None = Field(default=None, gt=0)
    organic: bool = False
    peat: bool = False


class SoilAnalysisIn(BaseModel):
    """A vision-model response, before it is allowed anywhere near the engine."""

    payload: dict[str, Any]
    model_provider: str
    model_name: str


class StepsRequest(BaseModel):
    foundation_type: str
    sector: str = "buildings_low_rise"
    findings: FindingsIn = FindingsIn()
