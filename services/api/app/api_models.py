"""Wire models for the persistence endpoints.

Responses never echo a password hash, and never include a field the caller is
not allowed to set. That is why these are separate from the ORM models rather
than serialised from them directly.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

SourceName = Literal["LABORATORY", "FIELD", "ENGINEER", "IMPORTED", "USER", "AI", "ESTIMATED"]
Role = Literal["guest", "free", "professional", "engineer", "admin"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    name: str | None = Field(default=None, max_length=200)
    #: Self-registration cannot mint an engineer or an admin. Those are granted.
    role: Literal["free", "professional"] = "free"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    role: str
    registration_no: str | None
    organization_id: uuid.UUID | None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sector: str = "buildings_low_rise"
    design_standard: str = "eurocode"
    client_name: str | None = Field(default=None, max_length=200)
    project_type: str | None = None
    country: str | None = None
    administrative_area: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    floors: int | None = Field(default=None, ge=1, le=200)
    basement: bool = False
    basement_depth_m: float | None = Field(default=None, ge=0, le=100)
    length_m: float | None = Field(default=None, gt=0, le=2000)
    width_m: float | None = Field(default=None, gt=0, le=2000)
    structural_system: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sector: str | None = None
    design_standard: str | None = None
    client_name: str | None = None
    project_type: str | None = None
    country: str | None = None
    administrative_area: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    floors: int | None = Field(default=None, ge=1, le=200)
    basement: bool | None = None
    basement_depth_m: float | None = Field(default=None, ge=0, le=100)
    length_m: float | None = Field(default=None, gt=0, le=2000)
    width_m: float | None = Field(default=None, gt=0, le=2000)
    structural_system: str | None = None
    status: Literal["draft", "active", "complete", "archived"] | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    client_name: str | None
    sector: str
    design_standard: str
    country: str | None
    administrative_area: str | None
    latitude: float | None
    longitude: float | None
    floors: int | None
    basement: bool
    status: str
    created_at: datetime
    updated_at: datetime


class BoreholeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    ground_elevation_m: float | None = None
    total_depth_m: float | None = Field(default=None, gt=0, le=500)
    groundwater_depth_m: float | None = Field(default=None, ge=0, le=500)
    #: Whether the water level was seen, or inferred. Not the same fact.
    groundwater_observed: bool = False
    groundwater_date: date | None = None
    drilling_method: str | None = None
    date_drilled: date | None = None
    notes: str | None = Field(default=None, max_length=4000)


class BoreholeResponse(BaseModel):
    id: uuid.UUID
    code: str
    ground_elevation_m: float | None
    total_depth_m: float | None
    groundwater_depth_m: float | None
    groundwater_observed: bool
    drilling_method: str | None
    date_drilled: date | None
    notes: str | None


class SoilLayerCreate(BaseModel):
    top_depth_m: float = Field(ge=0, le=500)
    bottom_depth_m: float = Field(gt=0, le=500)
    description: str | None = Field(default=None, max_length=1000)
    uscs_class: str | None = Field(default=None, max_length=10)
    aashto_class: str | None = Field(default=None, max_length=20)
    colour: str | None = None
    moisture: str | None = None
    consistency: str | None = None
    density: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    #: Required. No value enters the ground record without saying how it was obtained.
    classification_source: SourceName


class SoilLayerResponse(BaseModel):
    id: uuid.UUID
    top_depth_m: float
    bottom_depth_m: float
    description: str | None
    uscs_class: str | None
    aashto_class: str | None
    confidence: float | None
    classification_source: str


class ReclassifyRequest(BaseModel):
    uscs_class: str | None = Field(default=None, max_length=10)
    aashto_class: str | None = Field(default=None, max_length=20)
    classification_source: SourceName
    confidence: float | None = Field(default=None, ge=0, le=1)


class SptCreate(BaseModel):
    depth_m: float = Field(ge=0, le=500)
    seating_blows: int | None = Field(default=None, ge=0, le=200)
    blows_1: int | None = Field(default=None, ge=0, le=200)
    blows_2: int | None = Field(default=None, ge=0, le=200)
    blows_3: int | None = Field(default=None, ge=0, le=200)
    n_raw: int = Field(ge=0, le=200)
    energy_ratio_percent: float = Field(default=60.0, gt=0, le=100)
    borehole_diameter_mm: float = Field(default=100.0, gt=0, le=1000)
    rod_length_m: float = Field(default=6.0, gt=0, le=100)
    effective_overburden_kpa: float | None = Field(default=None, gt=0)


class CalculationResponse(BaseModel):
    id: uuid.UUID
    calculation_type: str
    method: str
    standard: str | None
    engine_version: str
    status: str
    preliminary: bool
    created_at: datetime
    results: dict[str, Any]
    warnings: list[Any]


class ReviewRequest(BaseModel):
    status: Literal["COMMENTS", "APPROVED", "REJECTED"]
    comments: str | None = Field(default=None, max_length=8000)
    report_id: uuid.UUID | None = None


class ReviewResponse(BaseModel):
    id: uuid.UUID
    status: str
    comments: str | None
    reviewer_id: uuid.UUID
    signed_at: datetime | None
    created_at: datetime


class ReportResponse(BaseModel):
    id: uuid.UUID
    report_type: str
    revision: int
    banner: str
    engine_version: str
    created_at: datetime
