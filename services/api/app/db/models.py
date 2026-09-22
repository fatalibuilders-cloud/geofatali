"""ORM models, mapped onto the hand-written schema.

The SQL migrations are the source of truth, not these classes. Nothing here
creates a table: the schema carries EXCLUDE constraints, triggers and CHECKs
that express engineering rules, and a model-first workflow would quietly lose
them. ``tests/test_schema_drift.py`` asserts that every column in the database
is mapped here and vice versa, so the two cannot drift apart unnoticed.

Columns deliberately not mapped:

  ``location`` on projects and boreholes — PostGIS GEOGRAPHY(Point, 4326).
  Mapping it needs geoalchemy2; until the map feature is built nothing reads
  it, and ``latitude``/``longitude`` carry the same information for the API.
  The column exists in the schema so the spatial index is ready.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

#: Columns that exist in the schema but are intentionally unmapped, with why.
UNMAPPED_COLUMNS: dict[str, dict[str, str]] = {
    "projects": {"location": "PostGIS geography; needs geoalchemy2, nothing reads it yet"},
    "boreholes": {"location": "PostGIS geography; needs geoalchemy2, nothing reads it yet"},
}

#: Tables owned by extensions or by the migration runner, not by the ORM.
NON_MODEL_TABLES = frozenset({"spatial_ref_sys", "schema_migrations"})


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())


# The enum types already exist in the database; create_type=False stops
# SQLAlchemy trying to create them again.
provenance_source = ENUM(
    "LABORATORY", "FIELD", "ENGINEER", "IMPORTED", "USER", "AI", "ESTIMATED",
    name="provenance_source", create_type=False,
)
user_role = ENUM(
    "guest", "free", "professional", "engineer", "admin",
    name="user_role", create_type=False,
)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(Text, unique=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(user_role, default="free")
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    #: An engineer's board registration. A review cannot be signed without one.
    registration_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str] = mapped_column(Text)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(Text)
    client_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    sector: Mapped[str] = mapped_column(Text, default="buildings_low_rise")
    project_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    administrative_area: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    floors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    basement: Mapped[bool] = mapped_column(Boolean, default=False)
    basement_depth_m: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    length_m: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    width_m: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    structural_system: Mapped[str | None] = mapped_column(Text, nullable=True)
    design_standard: Mapped[str] = mapped_column(Text, default="eurocode")
    status: Mapped[str] = mapped_column(Text, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    boreholes: Mapped[list["Borehole"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Borehole(Base):
    __tablename__ = "boreholes"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(Text)
    ground_elevation_m: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_depth_m: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    groundwater_depth_m: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    #: Observed and estimated groundwater are different facts (spec section 19).
    groundwater_observed: Mapped[bool] = mapped_column(Boolean, default=False)
    groundwater_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    drilling_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_drilled: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="boreholes")
    layers: Mapped[list["SoilLayer"]] = relationship(
        back_populates="borehole", cascade="all, delete-orphan",
        order_by="SoilLayer.top_depth_m",
    )


class SoilLayer(Base):
    __tablename__ = "soil_layers"

    id: Mapped[uuid.UUID] = _pk()
    borehole_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boreholes.id", ondelete="CASCADE")
    )
    top_depth_m: Mapped[Decimal] = mapped_column(Numeric)
    bottom_depth_m: Mapped[Decimal] = mapped_column(Numeric)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    uscs_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    aashto_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    colour: Mapped[str | None] = mapped_column(Text, nullable=True)
    moisture: Mapped[str | None] = mapped_column(Text, nullable=True)
    consistency: Mapped[str | None] = mapped_column(Text, nullable=True)
    density: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    #: NOT NULL by schema: no value enters this table without saying how it was obtained.
    classification_source: Mapped[str] = mapped_column(provenance_source)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    borehole: Mapped[Borehole] = relationship(back_populates="layers")


class SoilMedia(Base):
    __tablename__ = "soil_media"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    borehole_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boreholes.id", ondelete="SET NULL"), nullable=True
    )
    layer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("soil_layers.id", ondelete="SET NULL"), nullable=True
    )
    media_type: Mapped[str] = mapped_column(Text)
    #: An object-storage key. Never a public URL — access is by signed URL only.
    storage_key: Mapped[str] = mapped_column(Text)
    thumbnail_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("soil_media.id", ondelete="SET NULL"), nullable=True
    )
    model_provider: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SptTest(Base):
    __tablename__ = "spt_tests"

    id: Mapped[uuid.UUID] = _pk()
    borehole_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boreholes.id", ondelete="CASCADE")
    )
    depth_m: Mapped[Decimal] = mapped_column(Numeric)
    seating_blows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blows_1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blows_2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blows_3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Raw and corrected are stored apart so a correction cannot be applied twice.
    n_raw: Mapped[int] = mapped_column(Integer)
    n60: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    n1_60: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    correction_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_factors: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    equipment_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DcpTest(Base):
    __tablename__ = "dcp_tests"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    chainage: Mapped[str | None] = mapped_column(Text, nullable=True)
    depth_m: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    blows: Mapped[int] = mapped_column(Integer)
    penetration_mm: Mapped[Decimal] = mapped_column(Numeric)
    dcp_index: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    cbr_percent: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    subgrade_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CptTest(Base):
    __tablename__ = "cpt_tests"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    sounding_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    depth_m: Mapped[Decimal] = mapped_column(Numeric)
    qc_mpa: Mapped[Decimal] = mapped_column(Numeric)
    fs_kpa: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    pore_pressure_kpa: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    friction_ratio: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    behaviour_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LabTest(Base):
    __tablename__ = "lab_tests"

    id: Mapped[uuid.UUID] = _pk()
    soil_layer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("soil_layers.id", ondelete="CASCADE")
    )
    test_type: Mapped[str] = mapped_column(Text)
    test_standard: Mapped[str | None] = mapped_column(Text, nullable=True)
    results: Mapped[dict[str, Any]] = mapped_column(JSONB)
    laboratory: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Load(Base):
    __tablename__ = "loads"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    load_type: Mapped[str] = mapped_column(Text)
    value_kn: Mapped[Decimal] = mapped_column(Numeric)
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    #: USER for a load from a structural model, ESTIMATED for one the engine built.
    source: Mapped[str] = mapped_column(provenance_source)
    load_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Calculation(Base):
    """Append-only. A database trigger refuses UPDATE and DELETE on this table."""

    __tablename__ = "calculations"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    calculation_type: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(Text)
    standard: Mapped[str | None] = mapped_column(Text, nullable=True)
    standard_edition: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine_version: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
    results: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    preliminary: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Foundation(Base):
    __tablename__ = "foundations"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    foundation_type: Mapped[str] = mapped_column(Text)
    geometry: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    #: 'candidate' until an engineer selects it. Software never sets 'approved'.
    status: Mapped[str] = mapped_column(Text, default="candidate")
    calculation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calculations.id", ondelete="SET NULL"), nullable=True
    )
    construction_steps: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    """Append-only and revisioned. A new issue is a new row, never an edit."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    report_type: Mapped[str] = mapped_column(Text, default="geotechnical_assessment")
    revision: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    engine_version: Mapped[str] = mapped_column(Text)
    ai_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    banner: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    action: Mapped[str] = mapped_column(Text)
    entity: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    device_info: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    metric: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric, default=1)
    period_start: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
