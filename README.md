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
├── services/
│   ├── engineering-engine/   pure Python, no dependencies, 200 tests
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
│   └── api/                  FastAPI over the engine, 21 tests
├── database/migrations/      PostgreSQL + PostGIS schema
└── docs/
    ├── engineering/METHODS.md    every formula and its published source
    └── product/MVP-STATUS.md     what is built and what is not
```

## Run it

```bash
cd services/engineering-engine
pip install -e ".[dev]"
python -m pytest                       # 200 tests

cd ../api
pip install -r requirements.txt
PYTHONPATH=../engineering-engine python -m pytest tests    # 21 tests
PYTHONPATH=../engineering-engine uvicorn app.main:app --reload
# http://localhost:8000/docs
```

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
