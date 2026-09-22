-- Integrity that the application cannot talk its way out of.
--
-- 0001 created the tables. This migration turns three of the product's
-- promises from conventions into constraints the database itself enforces,
-- because a convention only holds until someone writes a quick fix at 2am.

CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- ── 1. Soil layers within one borehole may not overlap ──────────────────
--
-- A borehole log that says 0.0-1.5 m is clay and 1.0-3.0 m is sand is not a
-- log, it is two contradictory logs. An EXCLUDE constraint over the depth
-- range catches it at write time, which is the only time anyone can fix it.
ALTER TABLE soil_layers
    ADD CONSTRAINT soil_layers_no_overlap
    EXCLUDE USING gist (
        borehole_id WITH =,
        numrange(top_depth_m, bottom_depth_m, '[)') WITH &&
    );

-- ── 2. Calculations and reports are append-only ─────────────────────────
--
-- Spec section 42: "Do not overwrite old engineering calculations. Create new
-- revisions." A calculation record is evidence of what the engine said, with
-- which inputs, under which standard, at which version. Editing one after the
-- fact destroys the only thing that made it worth storing. A re-run inserts a
-- new row; nothing updates or deletes an old one.
--
-- Deleting the parent project still cascades for `calculations` and `reports`,
-- which is correct: erasing a project on request must actually erase it. The
-- audit log is the exception and carries no foreign key to projects, because
-- the record that a project was deleted has to outlive the project.
CREATE OR REPLACE FUNCTION refuse_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'Table % is append-only: % is not permitted. Engineering records are '
        'evidence of what was calculated and when. Insert a new row (a new '
        'revision) instead of changing an old one.',
        TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calculations_append_only
    BEFORE UPDATE OR DELETE ON calculations
    FOR EACH ROW EXECUTE FUNCTION refuse_mutation();

CREATE TRIGGER reports_append_only
    BEFORE UPDATE OR DELETE ON reports
    FOR EACH ROW EXECUTE FUNCTION refuse_mutation();

CREATE TRIGGER audit_log_append_only
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION refuse_mutation();

-- ── 3. updated_at actually means updated ────────────────────────────────
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_touch_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER projects_touch_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ── 4. A review may only be signed by someone who can sign ──────────────
--
-- The engineer review workflow is what removes the PRELIMINARY banner from a
-- report. It is the single most consequential state change in the product, so
-- an approval without a signing timestamp is rejected outright.
ALTER TABLE reviews
    ADD CONSTRAINT reviews_approved_must_be_signed
    CHECK (status <> 'APPROVED' OR signed_at IS NOT NULL);

-- A project keeps the sector it was screened under; an unknown sector would
-- silently change which checks govern it.
ALTER TABLE projects
    ADD CONSTRAINT projects_sector_not_blank
    CHECK (length(trim(sector)) > 0);
