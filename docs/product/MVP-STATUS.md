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
| 34 | Database schema | Migration written with provenance and immutability constraints |
| 35–36 | Calculation API | FastAPI over the engine; refusals are 200 with a status, impossible input is 422 |
| 51 | Testing | Unit, regression, property and integration tests |

## Not built yet

| Spec section | Component | Why it is not here |
|---|---|---|
| 4, 59 | Flutter Android application | The whole client. The API it will call is defined and running |
| 31 | Pile capacity calculations | Returns NOT_IMPLEMENTED by design; needs validation against load-test data before release |
| 32 | Video frame selection pipeline | Quality check, de-blur, dedupe, frame selection |
| 35 | Persistence layer and auth | Schema is written; no repository or endpoint layer over it yet |
| 41 | PDF rendering | The report is a structured document with a Markdown renderer; the PDF service is next |
| 43–45 | Subscriptions, payments, metering | Schema for usage exists; no billing |
| 46 | Admin dashboard | — |
| 48 | Offline mode and sync | Belongs with the mobile client |
| 52 | AI evaluation dataset | No accuracy claim may be published before this exists |
| 54 | Geotechnical map | PostGIS columns and indexes are in the migration, nothing reads them yet |
| 55–56 | OCR, drawing interpretation, BIM | Roadmap phases 3 and 4 |

## Acceptance criteria (spec section 62)

Of the twenty criteria, the engine and API cover the calculation half: entering
soil layers and field tests, running bearing capacity, sizing a footing, seeing
foundation candidates with their warnings and missing data, and every
calculation retaining its method, inputs, standard and engine version. The
remaining criteria — register, save, generate PDF, share, engineer review —
need the persistence layer, the PDF service and the mobile client.
