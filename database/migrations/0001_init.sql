-- GeoFatali — initial schema (spec section 34).
--
-- Two principles are enforced here rather than left to application code:
--
--   1. PROVENANCE. Any table that stores a geotechnical value stores where it
--      came from. `classification_source` and the `source` columns are NOT
--      NULL and constrained to the source vocabulary, so it is not possible to
--      write a number into this database without saying how it was obtained.
--
--   2. IMMUTABLE CALCULATIONS. `calculations` and `reports` are append-only by
--      convention and by revision: a re-run creates a new row, it never
--      updates an old one. An engineering record that can be silently edited
--      after the fact is not an engineering record.

CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- The vocabulary for how any value was obtained. Referenced by every table
-- that stores a measurable quantity.
CREATE TYPE provenance_source AS ENUM (
    'LABORATORY', 'FIELD', 'ENGINEER', 'IMPORTED', 'USER', 'AI', 'ESTIMATED'
);

CREATE TYPE user_role AS ENUM ('guest', 'free', 'professional', 'engineer', 'admin');

CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    owner_id    UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email             TEXT UNIQUE NOT NULL,
    phone             TEXT,
    name              TEXT,
    role              user_role NOT NULL DEFAULT 'free',
    organization_id   UUID REFERENCES organizations(id) ON DELETE SET NULL,
    -- A reviewer's registration number. Nothing may be signed off without it.
    registration_no   TEXT,
    password_hash     TEXT NOT NULL,
    subscription_id   UUID,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE organizations
    ADD CONSTRAINT organizations_owner_fk
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL;

CREATE TABLE projects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID REFERENCES organizations(id) ON DELETE SET NULL,
    created_by          UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name                TEXT NOT NULL,
    client_name         TEXT,
    -- The industry this project belongs to. It selects which checks govern,
    -- which foundations are candidates and what the investigation must cover.
    sector              TEXT NOT NULL DEFAULT 'buildings_low_rise',
    project_type        TEXT,
    country             TEXT,
    administrative_area TEXT,
    location            GEOGRAPHY(Point, 4326),
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    floors              INTEGER CHECK (floors IS NULL OR floors >= 1),
    basement            BOOLEAN NOT NULL DEFAULT FALSE,
    basement_depth_m    NUMERIC CHECK (basement_depth_m IS NULL OR basement_depth_m >= 0),
    length_m            NUMERIC CHECK (length_m IS NULL OR length_m > 0),
    width_m             NUMERIC CHECK (width_m IS NULL OR width_m > 0),
    structural_system   TEXT,
    design_standard     TEXT NOT NULL DEFAULT 'eurocode',
    status              TEXT NOT NULL DEFAULT 'draft',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX projects_location_idx ON projects USING GIST (location);
CREATE INDEX projects_created_by_idx ON projects (created_by);

CREATE TABLE boreholes (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id            UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code                  TEXT NOT NULL,
    location              GEOGRAPHY(Point, 4326),
    ground_elevation_m    NUMERIC,
    total_depth_m         NUMERIC CHECK (total_depth_m IS NULL OR total_depth_m > 0),
    groundwater_depth_m   NUMERIC CHECK (groundwater_depth_m IS NULL OR groundwater_depth_m >= 0),
    -- Spec section 19: an observed water level and an estimated one are not
    -- the same fact and are never stored as if they were.
    groundwater_observed  BOOLEAN NOT NULL DEFAULT FALSE,
    groundwater_date      DATE,
    drilling_method       TEXT,
    date_drilled          DATE,
    notes                 TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, code)
);
CREATE INDEX boreholes_location_idx ON boreholes USING GIST (location);

CREATE TABLE soil_layers (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    borehole_id           UUID NOT NULL REFERENCES boreholes(id) ON DELETE CASCADE,
    top_depth_m           NUMERIC NOT NULL CHECK (top_depth_m >= 0),
    bottom_depth_m        NUMERIC NOT NULL,
    description           TEXT,
    uscs_class            TEXT,
    aashto_class          TEXT,
    colour                TEXT,
    moisture              TEXT,
    consistency           TEXT,
    density               TEXT,
    confidence            NUMERIC CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    classification_source provenance_source NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (bottom_depth_m > top_depth_m)
);
CREATE INDEX soil_layers_borehole_idx ON soil_layers (borehole_id, top_depth_m);

CREATE TABLE soil_media (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    borehole_id   UUID REFERENCES boreholes(id) ON DELETE SET NULL,
    layer_id      UUID REFERENCES soil_layers(id) ON DELETE SET NULL,
    media_type    TEXT NOT NULL CHECK (media_type IN ('photo', 'video')),
    -- An object-storage key, never a public URL. Access is by signed URL only.
    storage_key   TEXT NOT NULL,
    thumbnail_key TEXT,
    captured_at   TIMESTAMPTZ,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ai_analyses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    media_id        UUID REFERENCES soil_media(id) ON DELETE SET NULL,
    model_provider  TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,
    result          JSONB NOT NULL,
    confidence      NUMERIC NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE spt_tests (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    borehole_id       UUID NOT NULL REFERENCES boreholes(id) ON DELETE CASCADE,
    depth_m           NUMERIC NOT NULL CHECK (depth_m >= 0),
    seating_blows     INTEGER,
    blows_1           INTEGER,
    blows_2           INTEGER,
    blows_3           INTEGER,
    -- Raw and corrected are stored separately and the method is named, so a
    -- correction can never be applied twice or applied invisibly.
    n_raw             INTEGER NOT NULL CHECK (n_raw >= 0),
    n60               NUMERIC,
    n1_60             NUMERIC,
    correction_method TEXT,
    correction_factors JSONB NOT NULL DEFAULT '{}'::jsonb,
    equipment_data    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX spt_borehole_idx ON spt_tests (borehole_id, depth_m);

CREATE TABLE dcp_tests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chainage        TEXT,
    depth_m         NUMERIC CHECK (depth_m IS NULL OR depth_m >= 0),
    blows           INTEGER NOT NULL CHECK (blows > 0),
    penetration_mm  NUMERIC NOT NULL CHECK (penetration_mm > 0),
    dcp_index       NUMERIC,
    cbr_percent     NUMERIC,
    subgrade_class  TEXT,
    method          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cpt_tests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    sounding_code   TEXT,
    depth_m         NUMERIC NOT NULL CHECK (depth_m >= 0),
    qc_mpa          NUMERIC NOT NULL,
    fs_kpa          NUMERIC,
    pore_pressure_kpa NUMERIC,
    friction_ratio  NUMERIC,
    behaviour_type  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX cpt_project_depth_idx ON cpt_tests (project_id, sounding_code, depth_m);

CREATE TABLE lab_tests (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    soil_layer_id  UUID NOT NULL REFERENCES soil_layers(id) ON DELETE CASCADE,
    test_type      TEXT NOT NULL,
    test_standard  TEXT,
    results        JSONB NOT NULL,
    laboratory     TEXT,
    test_date      DATE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE loads (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    label       TEXT,
    load_type   TEXT NOT NULL,
    value_kn    NUMERIC NOT NULL,
    area_m2     NUMERIC,
    -- 'USER' for a load from a structural model, 'ESTIMATED' for one the
    -- engine built from geometry. The report prints the difference.
    source      provenance_source NOT NULL,
    load_case   TEXT,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE calculations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    calculation_type TEXT NOT NULL,
    method           TEXT NOT NULL,
    standard         TEXT,
    standard_edition TEXT,
    engine_version   TEXT NOT NULL,
    status           TEXT NOT NULL,
    inputs           JSONB NOT NULL,
    results          JSONB NOT NULL DEFAULT '{}'::jsonb,
    warnings         JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance       JSONB NOT NULL DEFAULT '{}'::jsonb,
    preliminary      BOOLEAN NOT NULL DEFAULT TRUE,
    created_by       UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX calculations_project_idx ON calculations (project_id, created_at DESC);

CREATE TABLE foundations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    foundation_type TEXT NOT NULL,
    geometry        JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- 'candidate' until an engineer selects it. There is no 'approved' that
    -- the software can set by itself.
    status          TEXT NOT NULL DEFAULT 'candidate',
    calculation_id  UUID REFERENCES calculations(id) ON DELETE SET NULL,
    construction_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    report_type     TEXT NOT NULL DEFAULT 'geotechnical_assessment',
    revision        INTEGER NOT NULL CHECK (revision >= 1),
    storage_key     TEXT,
    document        JSONB NOT NULL,
    generated_by    UUID REFERENCES users(id) ON DELETE SET NULL,
    engine_version  TEXT NOT NULL,
    ai_model        TEXT,
    banner          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Spec section 42: revisions, never overwrites.
    UNIQUE (project_id, report_type, revision)
);

CREATE TABLE reviews (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    report_id    UUID REFERENCES reports(id) ON DELETE SET NULL,
    reviewer_id  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status       TEXT NOT NULL CHECK (status IN ('PENDING', 'COMMENTS', 'APPROVED', 'REJECTED')),
    comments     TEXT,
    signed_at    TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Spec section 50. Who changed what, when, and what it was before.
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    project_id  UUID REFERENCES projects(id) ON DELETE CASCADE,
    action      TEXT NOT NULL,
    entity      TEXT,
    entity_id   UUID,
    old_value   JSONB,
    new_value   JSONB,
    device_info JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_project_idx ON audit_log (project_id, created_at DESC);

-- Spec section 45. Metering is per organisation and per period.
CREATE TABLE usage_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    metric          TEXT NOT NULL,
    quantity        NUMERIC NOT NULL DEFAULT 1,
    period_start    DATE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX usage_records_period_idx ON usage_records (organization_id, metric, period_start);
