# GeoFatali

**AI-assisted geotechnical and foundation engineering.** A Fatalibuilders
product, and a separate application from the Fatali Builders construction app.

GeoFatali answers one question for anyone who has to build on ground:

> What is under this site, what can it carry, and what do I build on it — step
> by step?

It is not a building app. Geotechnical findings serve every industry that puts
load into the ground, and the engine treats the industry as a first-class
input. A house cares about bearing pressure and differential settlement. A road
cares about CBR. A dam cares about seepage and piping. A transmission tower
cares about uplift, because half its legs are in tension. A wind turbine cares
about rotational stiffness and twenty years of load cycles. **Twenty sectors**
are modelled, each with its own governing checks, its own settlement tolerance,
its own candidate foundations and its own definition of an adequate
investigation.

## The line this product does not cross

A phone camera cannot establish bearing capacity. GeoFatali never pretends
otherwise, and that is enforced in code rather than in a disclaimer:

- The vision model may describe what is **visible** — colour, texture, apparent
  grading, layering, moisture. It may propose a probable USCS class with a
  confidence.
- It may **not** return a bearing capacity, cohesion, friction angle, density,
  SPT value, groundwater level, settlement or a statement that a foundation is
  safe. `validate_ai_result` rejects any response containing one, and the API
  returns 422. A provider that starts inventing measurements cannot reach the
  calculation engine.
- Every value carries a **provenance**: LABORATORY, FIELD, ENGINEER, IMPORTED,
  USER, AI or ESTIMATED. A calculated result is preliminary unless every
  parameter it used was measured, and the report prints the table.
- A missing input produces `INSUFFICIENT_DATA` naming the test that would
  supply it — never a plausible substitute.
- Foundation screening returns **candidates**, never one approved foundation.

## What is here

```
geofatali/
├── apps/
│   └── mobile/               Flutter Android client, 23 tests
├── services/
│   ├── engineering-engine/   pure Python, no dependencies, 202 tests
│   │   └── geofatali_engine/
│   │       ├── standards.py      design standards and load combinations as data
│   │       ├── sectors.py        20 industries and what governs each
│   │       ├── provenance.py     where every number came from
│   │       ├── warnings.py       INFO / WARNING / CRITICAL, and refusals
│   │       ├── record.py         the reproducible calculation record
│   │       ├── soil/             USCS classification; SPT, DCP, CPT correlations
│   │       ├── bearing/          Terzaghi, Meyerhof, Hansen, Vesic
│   │       ├── settlement/       elastic, 1D consolidation, time rate
│   │       ├── loads/            preliminary Gk/Qk build-up
│   │       ├── foundations/      sizing, screening, and the construction steps
│   │       ├── report/           the 23-section report model
│   │       └── ai/               provider abstraction and the guardrails
│   └── api/                  FastAPI, persistence and auth, 89 tests
│       └── app/
│           ├── db/               engine, models, migration runner
│           ├── repositories/     the only code that touches the database
│           ├── routers/          auth, projects, ground record, calculations
│           └── security.py       Argon2id, JWT, roles
├── database/migrations/      PostgreSQL + PostGIS schema, applied in order
├── scripts/test-db.sh        starts a throwaway database for the tests
├── .github/workflows/        CI: backend tests, and the Android APK build
└── docs/
    ├── engineering/METHODS.md    every formula and its published source
    └── product/MVP-STATUS.md     what is built and what is not
```

## Run the backend

```bash
cp .env.example .env
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env
docker compose up
```

PostgreSQL with PostGIS, migrations applied, and the API on port 8000 bound to
every interface. It prints the addresses it can be reached on at startup.

## Run the tests

```bash
./run-tests.sh          # 291 tests: engine, API, and persistence

# or separately
cd services/engineering-engine && pip install -e ".[dev]" && python -m pytest
cd ../api && pip install -r requirements.txt
eval "$(../../scripts/test-db.sh)"      # a throwaway PostgreSQL + PostGIS
PYTHONPATH=../engineering-engine python -m pytest

# run it
export DATABASE_URL=postgresql://user:pass@host/geofatali
export JWT_SECRET=$(openssl rand -hex 32)
PYTHONPATH=../engineering-engine uvicorn app.main:app --reload
# http://localhost:8000/docs
```

The persistence tests run against a real PostgreSQL database, not SQLite. The
schema's value is in its constraints — an EXCLUDE that stops two soil layers
claiming the same depth, triggers that refuse UPDATE on a stored calculation, a
PostGIS column — and a substitute database has none of them.

## A worked example

Four storeys on black cotton clay on the eastern edge of Nairobi — the
commonest hard case in the home market.

```python
from geofatali_engine.soil.uscs import IndexTests, classify_uscs, swell_potential
from geofatali_engine.soil import correlations as corr
from geofatali_engine.bearing.capacity import SoilParameters, Footing, bearing_capacity
from geofatali_engine.foundations.screening import ScreeningInput, screen_foundations
from geofatali_engine.foundations.steps import GroundFindings
from geofatali_engine.provenance import Source

soil_class = classify_uscs(IndexTests(fines_percent=78, liquid_limit=64, plastic_limit=24))
# -> CH, fat clay, swell potential VERY_HIGH

spt = corr.correct_spt(n_raw=6, rod_length_m=3, effective_overburden_kpa=24.8)
cu = corr.undrained_strength_from_spt(spt.n60)     # marked ESTIMATED, with its scatter

record = bearing_capacity(
    soil=SoilParameters(unit_weight_kn_m3=16.5, cohesion_kpa=cu.value,
                        analysis="undrained", cohesion_source=Source.ESTIMATED),
    footing=Footing(width_m=1.5, depth_m=1.5, shape="square"),
    method="hansen", standard_id="kebs",
)
record.is_preliminary        # True — Cu was correlated, not measured

screen = screen_foundations(ScreeningInput(
    sector_id="buildings_low_rise",
    findings=GroundFindings(expansive_clay=True, swell_potential="VERY_HIGH",
                            black_cotton_depth_m=2.5, seismic_pga_g=0.07),
    # ... loads, capacity, settlement
))
```

The screen ranks **ground improvement with a shallow foundation** first, marks
the plain strip footing `CANDIDATE_WITH_CONDITIONS` with a `FAIL` on ground
conditions, and returns the construction sequence that starts:

```
 1. [HOLD] Remove or isolate the expansive clay      <- Expansive clay identified
 2.        Set out and confirm levels
 3.        Excavate the trench to founding level
 4. [HOLD] Inspect the founding stratum
 ...
11.        Keep water away from the foundation for the life of the building
12. [HOLD] Record what was built, and by whom
```

Steps marked `HOLD` are where work stops until an engineer has inspected.
Steps with an arrow were added because of what the investigation found on
**this** site.

## What the database will not let you do

Four of the product's promises are constraints, not conventions:

- **A soil layer cannot overlap another** in the same borehole. A log saying
  0.0–1.5 m is clay and 1.0–3.0 m is sand is two contradictory logs, and an
  `EXCLUDE` constraint catches it at write time, when someone can still fix it.
- **A stored calculation cannot be edited or deleted.** A trigger refuses both.
  A re-run inserts a new row; the history keeps every version, including the
  runs that returned `INSUFFICIENT_DATA`.
- **A value cannot be stored without its provenance.** `classification_source`
  is `NOT NULL`, so nothing enters the ground record without saying whether it
  came from a laboratory, the field, an engineer or the vision model.
- **An approval cannot exist without a signature.** A `CHECK` rejects an
  `APPROVED` review with no `signed_at`, and the application requires the
  reviewer to hold the engineer role and a board registration number.

One user cannot see another's site data: every read is scoped by the requesting
account, and someone else's project returns 404 rather than 403 — a 403 would
confirm the id exists.

## The Android app

`apps/mobile` is a Flutter client for the API: sign in, create a project,
log a borehole and its strata, run a bearing capacity calculation, screen the
foundation options, and read the construction sequence for the one you choose —
with the hold points marked and the steps that exist because of *this* site
labelled with what triggered them.

It is a client, not a copy: the phone stores nothing but your session, and on
first launch it asks for the address of your GeoFatali server. That is
deliberate — the engineering runs in one place, where it is tested.

The APK is built by GitHub Actions rather than on a laptop.
**[docs/product/ANDROID.md](docs/product/ANDROID.md)** covers getting it onto a
phone, running a backend it can reach, and what Google Play needs.

```bash
cd apps/mobile
flutter pub get
flutter test        # 23 tests
flutter analyze
```

## Where this sits

The engine is deliberately dependency-free and knows nothing about HTTP,
databases or any AI vendor. That is what makes every number it produces
reproducible from stored inputs, testable, and safe to move to another runtime.

The Flutter Android client, persistence, PDF rendering, billing and the pile
module are not built yet. `docs/product/MVP-STATUS.md` says exactly what is
done and what is not, section by section against the specification.

---

Nothing this software produces is a foundation design, and nothing it produces
certifies a structure as safe. Final geotechnical and structural design must be
carried out and sealed by an engineer registered in the project's jurisdiction.
