# GeoFatali API

```bash
pip install -r requirements.txt
pip install -e ../engineering-engine
uvicorn app.main:app --reload
```

Then open `http://localhost:8000/docs`.

The service holds no state yet: it validates a request, calls the engine and
returns the engine's calculation record. Persistence (projects, boreholes,
media, reports, reviews) is the next stage and its schema is already written
in `database/migrations/0001_init.sql`.
