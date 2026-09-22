# MVP status against the specification

Honest state of the build. "Done" means implemented and covered by tests that
run in CI; nothing is listed as done because it is half-written.

## Done

| Spec section | Component | Notes |
|---|---|---|
| 22–26 | Bearing capacity engine | Terzaghi, Meyerhof, Hansen, Vesic; shape, depth, inclination, ground-slope, base-tilt and water-table corrections; gross and net allowable |
| 25–26 | Footing sizing and eccentricity | Iterative sizing to convergence; middle-third and partial-contact pressure; sliding check |
| 27 | Settlement | Elastic and 1D consolidation, NC and OC including the σ'p crossing; secondary compression; time-rate |
| 20–21 | Load estimation | Tributary build-up, Gk/Qk kept apart, EN 1991-1-1 imposed-load reduction, always labelled preliminary |
| 12 | USCS classification | Full ASTM D2487 including dual symbols |
| 15–17 | SPT, DCP, CPT correlations | Corrections reported factor by factor; every correlation labelled ESTIMATED with its scatter |
| 28–30 | Foundation screening | Rules-based, transparent criteria, candidates never a single approval |
| — | Construction step sequences | Per foundation type, adapted to the ground found and the sector |
| 47 | Standards as data | Five standard configurations, load combinations and limits as data |
| — | Sector model | 20 industries, each with its own governing checks, limits, candidates and required investigation |
| 33, 53 | AI boundary | Provider abstraction, the published prompt, and validation that rejects any fabricated measurement |
| 39–40 | Validation and warnings | INFO/WARNING/CRITICAL; missing input produces INSUFFICIENT_DATA naming the test that would fix it |
| 24, 36 | Calculation records | Method, standard, edition, engine version, inputs, provenance and warnings on every result |
| 41–42 | Report model | All 23 sections, standing limitations, revision control, Markdown renderer |
| 34 | Database schema | Applied against real PostgreSQL 16 + PostGIS; provenance NOT NULL, EXCLUDE over layer depths, append-only triggers |
| 35–36 | Calculation API | FastAPI over the engine; refusals are 200 with a status, impossible input is 422 |
| 35 | Persistence | Projects, boreholes, soil layers, SPT/DCP/CPT, lab tests, calculations, foundations, reports, reviews, audit log |
| 6, 49 | Authentication and access control | Argon2id passwords, short-lived JWTs, five roles; every read scoped by user, a stranger's project is 404 not 403 |
| 42, 50 | Immutability and audit | Calculations, reports and audit rows are append-only in the database; reports are revisioned |
| 47 | Migrations | Numbered SQL files, applied in order, checksummed — an edited migration is refused |
| 57 | Docker development environment | `docker compose up` brings up PostGIS, applies migrations and serves the API on every interface |
| 51 | Testing | Unit, regression, property, integration and persistence tests, the last against a real database |
| 4, 7, 59 | Flutter Android client | Auth, projects, boreholes, soil layers with a drawn profile, SPT, bearing capacity, foundation screening and the construction steps |
| 60 | Design system | Engineering-software look: restrained palette, tabular figures, provenance on every value, preliminary banner throughout |
| — | Android release build | CI builds a sideloadable APK on every push and a Play App Bundle on a version tag |

## Not built yet

| Spec section | Component | Why it is not here |
|---|---|---|
| 48 | Offline mode and sync on the client | The app needs the server for everything; a borehole log is exactly what you record with no signal |
| 31 | Pile capacity calculations | Returns NOT_IMPLEMENTED by design; needs validation against load-test data before release |
| 32 | Video frame selection pipeline | Quality check, de-blur, dedupe, frame selection |
| 41 | PDF rendering | Reports are stored as a structured document plus Markdown; the PDF service is next |
| 10, 34 | Media upload | `soil_media` is in the schema; no object storage or signed-URL layer yet |
| 43–45 | Subscriptions, payments, metering | Schema for usage exists; no billing |
| 46 | Admin dashboard | — |
| 52 | AI evaluation dataset | No accuracy claim may be published before this exists |
| 54 | Geotechnical map | PostGIS columns and indexes are in the migration, nothing reads them yet |
| 55–56 | OCR, drawing interpretation, BIM | Roadmap phases 3 and 4 |

## Acceptance criteria (spec section 62)

Seventeen of the twenty now pass end to end, proved by
`services/api/tests/test_workflow.py`, which runs the whole path against a real
database: register, create a project, select the sector, enter building
information, create a borehole, add soil layers, enter SPT data, enter a load,
run bearing capacity, size a footing, see foundation candidates with their
warnings and missing data, save the project, review it as an engineer, and
retain method, inputs, standard and engine version on every calculation.

Outstanding: uploading a soil photo and receiving AI observations (needs object
storage and a configured vision provider), and generating and sharing a PDF
(the report is assembled and stored; only the rendering is missing).
