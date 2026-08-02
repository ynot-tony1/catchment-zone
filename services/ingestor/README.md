# catchment-zone: ingestion service

Data ingestion service for catchment-zone. Pulls officially published,
public data (GIAS establishment and trust extracts, DfE Explore Education
Statistics releases, and local authority catchment boundary datasets) into
the shared database, on a schedule.

This service never stores a user's submitted home address or postcode.
Postcode lookup for an individual user is the web app's concern; this
service only writes officially published, public source data.

For the full documentation (data source policy, coverage status, the
ethical and legal constraints this service is built under, and the
IngestionRun operational model), see `/docs/ingestion.md` at the repo root.

## Quick start

```bash
cd services/ingestor
uv venv .venv --python 3.12
uv pip install -e ".[dev]" --python .venv/bin/python
source .venv/bin/activate

ruff check .
mypy src
pytest

ingestor --help
```

Configuration is read from environment variables (see `.env.example` at the
repo root, particularly `INGEST_DATABASE_URL`) and from the version-controlled
registries under `config/` (`catchment-sources.yml`, `statistics-sources.yml`,
`metric-definitions.yml`).
