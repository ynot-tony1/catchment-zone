# Ingestion

The ingestion service lives in `services/ingestor` (Python 3.12, Typer CLI,
Docker image). It is the only thing in this project allowed to write to
CockroachDB with anything beyond read-only or narrow application privileges,
and it always runs in GitHub Actions or a local developer shell, never as
part of the Vercel build.

## Commands

```text
ingestor discover-gias      Check GIAS for a new establishment/group extract, without importing
ingestor import-gias        Stream-parse and upsert the current GIAS extract (--dry-run, --row-limit, --force)
ingestor import-trusts      Import trust records and trust/school relationships
ingestor import-statistics  Pull configured EES publications, map to SchoolMetric rows
ingestor import-performance Pull school performance measures
ingestor import-catchments  Import configured catchment sources (--local-authority, --academic-year, --dry-run, --geometry-validation-only, --force)
ingestor import-admissions  Import admission arrangement metadata
ingestor refresh-metrics    Recompute any derived/aggregate metrics from raw imported values
ingestor verify             Post-import sanity checks (row counts, referential integrity, geometry validity)
ingestor cleanup            Prune expired PostcodeCache rows, superseded display geometry, old successful IngestionRun rows
ingestor run                Run the full pipeline in order
```

## Design rules

- **Stream, don't load.** GIAS and EES files are processed in batches (see
  `services/ingestor/src/schoolscope_ingestor/db.py`), never read fully into
  memory before the first row is written.
- **Batch writes.** Upserts use batched `executemany`/multi-row statements,
  never one `INSERT` per row.
- **Checksum before import.** Every source records a SHA-256 checksum of the
  retrieved file or feature response; an unchanged checksum skips the import
  and records `SKIPPED_UNCHANGED` on the `IngestionRun`, unless `--force` is
  passed.
- **Defensive parsing.** A malformed row is rejected and counted, not a
  reason to abort the whole run. `ingestor verify` is what catches a
  systemic problem (e.g. a changed header layout) after the fact.
- **Preserve on failure.** A failed catchment import for one local authority
  does not touch the previously valid `CatchmentArea` rows for that
  authority; the previous valid version stays live until a new import
  succeeds and is verified.
- **Transactional per source.** Each `CatchmentSource` import is one
  transaction: either the whole source's boundaries land, or none do.

## Geometry pipeline

1. Query the configured source (currently: ArcGIS Feature Service `/query`
   endpoint with `f=geojson`).
2. Reproject to WGS84 if the source CRS is not already EPSG:4326 (pyproj).
3. Validate and, where possible, conservatively repair each geometry
   (Shapely). Reject and log, rather than crash on, an unrepairable geometry.
4. Compute bounding-box columns.
5. Produce a simplified display geometry for low zoom levels.
6. Compute a geometry checksum.
7. Write `CatchmentSource` and `CatchmentArea` rows inside one transaction.

## Running locally

```bash
cd services/ingestor
pip install -e ".[dev]"
cp ../../.env.example ../../.env   # fill in local values, never commit
ingestor run --dry-run
```

Docker:

```bash
docker compose --profile ingestion build ingestor
docker compose --profile ingestion run --rm ingestor ingestor verify
```

## Scheduling

See `.github/workflows/ingest-gias.yml` (daily check),
`ingest-school-statistics.yml` (weekly), and `ingest-catchments.yml`
(weekly). All three respect the `INGESTION_ENABLED` /
`CATCHMENT_INGESTION_ENABLED` repository variables as a kill switch, support
manual `workflow_dispatch` with dry-run and override inputs, and use a
concurrency group so overlapping runs queue rather than race.
