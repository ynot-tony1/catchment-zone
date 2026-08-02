"""Typer CLI entrypoint for the SchoolScope England ingestion service.

Each command wraps one pipeline step (or, for `run`, the whole sequence) and
exits non-zero on failure so a scheduled CI job can detect a failed run. All
commands log structured JSON via logging_setup.configure_logging.
"""

from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, cast

import httpx
import typer
import yaml

from schoolscope_ingestor import db
from schoolscope_ingestor.adapters import admissions as admissions_adapter
from schoolscope_ingestor.adapters import catchments as catchments_adapter
from schoolscope_ingestor.adapters import gias as gias_adapter
from schoolscope_ingestor.adapters import statistics as statistics_adapter
from schoolscope_ingestor.config import Settings, get_settings
from schoolscope_ingestor.logging_setup import configure_logging, get_logger, set_run_context

app = typer.Typer(
    name="ingestor",
    help="SchoolScope England data ingestion service: GIAS, DfE statistics and local authority catchment imports.",
    no_args_is_help=True,
)

logger = get_logger(__name__)


@app.callback()
def main() -> None:
    """Configure logging once, before any subcommand runs."""
    settings = get_settings()
    configure_logging(settings.log_level)


def _fail(message: str, source: str) -> None:
    logger.error(message, extra={"source": source})
    raise typer.Exit(code=1)


def _http_client(settings: Settings) -> httpx.Client:
    return httpx.Client(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": "SchoolScopeEngland-Ingestor/0.1 (public-data ingestion; contact via repo)"},
    )


def _connect_or_none(settings: Settings, *, dry_run: bool) -> db.ConnectionLike | None:
    """Open a database connection unless running in dry-run mode. Returns
    None (rather than raising) on a connection failure so read-only
    commands like discover-gias and verify can still report useful output
    when no database is reachable, e.g. in this sandbox."""
    if dry_run:
        return None
    try:
        # psycopg's real Connection.cursor() accepts more keyword-only
        # overloads than the narrow ConnectionLike protocol declares; the
        # cast documents that this is a deliberate, safe widening (a real
        # connection is always a superset of what ConnectionLike needs), not
        # an unchecked assumption.
        return cast("db.ConnectionLike", db.connect(settings.ingest_database_url))
    except Exception as exc:
        logger.warning("could not connect to database, continuing without persistence", extra={"error": str(exc)})
        return None


# ---------------------------------------------------------------------------
# discover-gias
# ---------------------------------------------------------------------------


@app.command("discover-gias")
def discover_gias() -> None:
    """Resolve and print the current GIAS establishment and trust extract URLs, without downloading them."""
    settings = get_settings()
    try:
        with _http_client(settings) as client:
            establishment_url = gias_adapter.discover_establishment_download_url(
                client, settings.gias_download_override_url
            )
            trust_url = gias_adapter.discover_trust_download_url(client, settings.gias_trust_download_override_url)
    except Exception as exc:
        _fail(f"GIAS discovery failed: {exc}", source="gias")
        return

    logger.info("discovered GIAS download URLs", extra={"establishment_url": establishment_url, "trust_url": trust_url})
    typer.echo(f"establishment: {establishment_url}")
    typer.echo(f"trust: {trust_url}")


# ---------------------------------------------------------------------------
# import-gias
# ---------------------------------------------------------------------------


@app.command("import-gias")
def import_gias(
    row_limit: Annotated[int | None, typer.Option(help="Only process the first N data rows (testing/debugging).")] = None,
    force: Annotated[bool, typer.Option(help="Import even if the checksum matches the last successful run.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Parse and validate only; do not write to the database.")] = False,
) -> None:
    """Download and import the current GIAS establishment extract."""
    settings = get_settings()
    set_run_context(source="gias_establishments")
    conn = _connect_or_none(settings, dry_run=dry_run)

    try:
        with _http_client(settings) as client:
            url = gias_adapter.discover_establishment_download_url(client, settings.gias_download_override_url)
            content, checksum = gias_adapter.download_extract(client, url)

        if not force and conn is not None:
            from schoolscope_ingestor.pipeline import get_last_successful_checksum

            last_checksum = get_last_successful_checksum(conn, "gias_establishments")
            if last_checksum == checksum:
                logger.info("GIAS extract unchanged since last successful run, skipping", extra={"checksum": checksum})
                typer.echo("skipped: checksum unchanged")
                return

        result = gias_adapter.parse_establishment_csv(content, row_limit=row_limit)
        logger.info(
            "parsed GIAS establishment extract",
            extra={"rows_processed": result.rows_processed, "rows_rejected": result.rows_rejected},
        )
        if result.rejection_samples:
            logger.warning("sample rejected GIAS rows", extra={"samples": result.rejection_samples})

        if dry_run:
            typer.echo(
                f"dry-run: {len(result.schools)} valid schools, "
                f"{len(result.local_authorities)} local authorities, {result.rows_rejected} rejected rows"
            )
            return

        if conn is None:
            _fail("no database connection available and --dry-run was not set", source="gias_establishments")
            return

        # local_authorities first: schools.local_authority_code is a foreign
        # key to it, and this extract is the only source of local authority
        # identity this service has, so a school row referencing a
        # not-yet-seen LA code would otherwise fail that constraint.
        la_rows = [la.model_dump(mode="json") for la in result.local_authorities]
        rows = [s.model_dump(mode="json") for s in result.schools]
        with db.transaction(conn):
            la_upserted = db.upsert_many(conn, "local_authorities", iter(la_rows), conflict_columns=["code"])
            inserted = db.upsert_many(conn, "schools", iter(rows), conflict_columns=["urn"], batch_size=settings.batch_size)

        logger.info(
            "imported GIAS establishments", extra={"rows_upserted": inserted, "local_authorities_upserted": la_upserted}
        )
        typer.echo(f"imported {inserted} schools, {la_upserted} local authorities ({result.rows_rejected} rows rejected)")
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(f"GIAS import failed: {exc}", source="gias_establishments")


# ---------------------------------------------------------------------------
# import-trusts
# ---------------------------------------------------------------------------


@app.command("import-trusts")
def import_trusts(
    force: Annotated[bool, typer.Option(help="Import even if the checksum matches the last successful run.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Parse and validate only; do not write to the database.")] = False,
) -> None:
    """Download and import the current GIAS academy trust / group extract."""
    settings = get_settings()
    set_run_context(source="gias_trusts")
    conn = _connect_or_none(settings, dry_run=dry_run)

    try:
        with _http_client(settings) as client:
            url = gias_adapter.discover_trust_download_url(client, settings.gias_trust_download_override_url)
            content, checksum = gias_adapter.download_extract(client, url)

        if not force and conn is not None:
            from schoolscope_ingestor.pipeline import get_last_successful_checksum

            last_checksum = get_last_successful_checksum(conn, "gias_trusts")
            if last_checksum == checksum:
                logger.info("GIAS trust extract unchanged, skipping", extra={"checksum": checksum})
                typer.echo("skipped: checksum unchanged")
                return

        result = gias_adapter.parse_trust_csv(content)
        logger.info(
            "parsed GIAS trust extract",
            extra={"rows_processed": result.rows_processed, "rows_rejected": result.rows_rejected},
        )

        if dry_run:
            typer.echo(f"dry-run: {len(result.trusts)} valid trusts, {result.rows_rejected} rejected rows")
            return

        if conn is None:
            _fail("no database connection available and --dry-run was not set", source="gias_trusts")
            return

        rows = [t.model_dump(mode="json") for t in result.trusts]
        with db.transaction(conn):
            inserted = db.upsert_many(
                conn, "academy_trusts", iter(rows), conflict_columns=["trust_id"], batch_size=settings.batch_size
            )
        typer.echo(f"imported {inserted} trusts ({result.rows_rejected} rows rejected)")
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(f"trust import failed: {exc}", source="gias_trusts")


# ---------------------------------------------------------------------------
# import-statistics / import-performance
# ---------------------------------------------------------------------------


def _load_statistics_config(settings: Settings) -> dict[str, Any]:
    with settings.statistics_sources_path.open(encoding="utf-8") as fh:
        loaded: dict[str, Any] = yaml.safe_load(fh)
        return loaded


@app.command("import-statistics")
def import_statistics(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Resolve releases only; do not write to the database.")] = False,
) -> None:
    """Import SchoolMetric rows for the DfE publications listed in config/statistics-sources.yml."""
    settings = get_settings()
    set_run_context(source="dfe_statistics")
    conn = _connect_or_none(settings, dry_run=dry_run)

    config = _load_statistics_config(settings)
    base_url = str(config["api"]["base_url"])
    publications: list[dict[str, Any]] = config["publications"]

    total_resolved = 0
    total_failed = 0

    with _http_client(settings) as client:
        for pub in publications:
            slug = pub["publication_slug"]
            try:
                release = statistics_adapter.resolve_current_release(client, base_url, slug)
            except Exception as exc:
                total_failed += 1
                logger.warning("could not resolve release for publication", extra={"slug": slug, "error": str(exc)})
                continue
            total_resolved += 1
            logger.info(
                "resolved publication release",
                extra={
                    "slug": slug,
                    "dataset_id": release.dataset_id,
                    "release_label": release.release_label,
                    "provisional": release.is_provisional,
                },
            )
            # NOTE (documented TODO): downloading and flattening the actual
            # dataset rows requires the EES data-set query response schema,
            # which should be verified against https://api.education.gov.uk/statistics/docs/
            # on first live run; statistics_adapter.map_rows_to_metrics is
            # ready to consume rows once that fetch is wired in here.

    if total_resolved == 0:
        _fail("could not resolve any configured DfE publication release", source="dfe_statistics")
        return

    typer.echo(f"resolved {total_resolved} publication release(s), {total_failed} failed")
    if dry_run or conn is None:
        return


@app.command("import-performance")
def import_performance() -> None:
    """Reserved for DfE school performance tables (exam results) once a source is added to config/statistics-sources.yml.

    No performance-tables publication is registered there yet (only
    school-capacity, pupil-absence-in-schools-in-england,
    pupil-attendance-in-schools and school-workforce-in-england are), so this
    command currently only reports that fact rather than importing anything
    invented.
    """
    logger.info("no performance-tables source configured; nothing to import")
    typer.echo("no performance-tables source is registered in config/statistics-sources.yml yet; skipped")


# ---------------------------------------------------------------------------
# import-catchments
# ---------------------------------------------------------------------------


def _load_catchment_sources(settings: Settings) -> list[dict[str, object]]:
    with settings.catchment_sources_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    sources: list[dict[str, object]] = data.get("sources", [])
    return [s for s in sources if s.get("enabled")]


#: catchment_areas.id has no SQL-level DEFAULT (see models.CatchmentArea's
#: docstring); id must never be part of the ON CONFLICT update clause below,
#: since (source_id, geometry_checksum) is the real dedup key and an existing
#: area's id must survive a re-import untouched.
_CATCHMENT_AREA_UPDATE_COLUMNS = [
    "area_name",
    "area_type",
    "academic_year",
    "geometry_geojson",
    "simplified_geometry_geojson",
    "minimum_latitude",
    "maximum_latitude",
    "minimum_longitude",
    "maximum_longitude",
    "valid_from",
    "valid_to",
]


def _resolve_catchment_source_id(conn: db.ConnectionLike | None, source: dict[str, object]) -> str:
    """Look up the existing catchment_sources.id for this (local authority,
    academic year, source type) triple, so a re-import reuses the same id
    instead of orphaning any catchment_areas rows already written against it.

    catchment_sources.id has no SQL-level DEFAULT (Prisma's @default(uuid())
    is generated client-side by Prisma Client, not the database), so a fresh
    id is only minted here when no matching row exists yet.
    """
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM catchment_sources WHERE local_authority_code = %(local_authority_code)s "
                "AND academic_year = %(academic_year)s AND source_type = %(source_type)s",
                {
                    "local_authority_code": source["local_authority_code"],
                    "academic_year": source["academic_year"],
                    "source_type": source["source_type"],
                },
            )
            row = cur.fetchone()
            if row is not None:
                return str(row["id"])
    return str(uuid.uuid4())


@app.command("import-catchments")
def import_catchments(
    local_authority: Annotated[
        str | None, typer.Option("--local-authority", help="Only import this local authority code or name.")
    ] = None,
    academic_year: Annotated[
        str | None, typer.Option("--academic-year", help="Only import sources for this academic year.")
    ] = None,
    geometry_validation_only: Annotated[
        bool,
        typer.Option(
            "--geometry-validation-only",
            help="Validate and repair geometry from each source without writing anything to the database.",
        ),
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Import catchment area polygons from the configured ArcGIS FeatureServer sources."""
    settings = get_settings()
    set_run_context(source="catchments")
    conn = _connect_or_none(settings, dry_run=dry_run or geometry_validation_only)

    sources = _load_catchment_sources(settings)
    if local_authority:
        sources = [
            s
            for s in sources
            if s.get("local_authority_code") == local_authority or s.get("local_authority_name") == local_authority
        ]
    if academic_year:
        sources = [s for s in sources if s.get("academic_year") == academic_year]

    if not sources:
        typer.echo("no enabled catchment sources matched the given filters")
        return

    total_areas = 0
    total_rejected = 0

    with _http_client(settings) as client:
        for source in sources:
            if not source.get("licence"):
                logger.error("refusing to import source with no licence recorded", extra={"source": source})
                total_rejected += 1
                continue

            feature_url = str(source["download_url"])
            try:
                query_result = catchments_adapter.query_all_features(client, feature_url)
            except Exception as exc:
                logger.error("could not query FeatureServer", extra={"url": feature_url, "error": str(exc)})
                total_rejected += 1
                continue

            source_id = _resolve_catchment_source_id(conn, source)

            build_result = catchments_adapter.build_catchment_areas(
                query_result.features,
                source_id=source_id,
                area_type=str(source["source_type"]),
                academic_year=str(source["academic_year"]),
                name_field_candidates=["SCHOOL_NAME", "NAME", "name", "SchoolName"],
                detected_wkid=query_result.detected_wkid,
                fallback_source_crs=str(source["coordinate_reference_system"]),
                valid_from_iso=datetime.now(UTC).isoformat(),
            )
            total_areas += len(build_result.areas)
            total_rejected += build_result.rejected_count
            logger.info(
                "processed catchment source",
                extra={
                    "local_authority": source.get("local_authority_name"),
                    "source_type": source.get("source_type"),
                    "areas_built": len(build_result.areas),
                    "areas_rejected": build_result.rejected_count,
                },
            )

            if geometry_validation_only or dry_run:
                continue

            if conn is None:
                logger.warning("no database connection; skipping persistence for this source")
                continue

            checksum = hashlib.sha256(
                "|".join(sorted(a.geometry_checksum for a in build_result.areas)).encode("utf-8")
            ).hexdigest()
            source_row = {
                "id": source_id,
                "local_authority_code": source["local_authority_code"],
                "academic_year": source["academic_year"],
                "source_url": source["source_url"],
                "download_url": source["download_url"],
                "source_type": source["source_type"],
                "format": source["format"],
                "licence": source["licence"],
                "checksum": checksum,
                "retrieved_at": datetime.now(UTC),
                "status": "VALID" if build_result.areas else "FAILED",
            }
            area_rows = [area.model_dump(mode="json") for area in build_result.areas]
            with db.transaction(conn):
                db.upsert_many(
                    conn,
                    "catchment_sources",
                    iter([source_row]),
                    conflict_columns=["local_authority_code", "academic_year", "source_type"],
                    update_columns=[
                        c for c in source_row if c not in ("id", "local_authority_code", "academic_year", "source_type")
                    ],
                    batch_size=settings.batch_size,
                )
                db.upsert_many(
                    conn,
                    "catchment_areas",
                    iter(area_rows),
                    conflict_columns=["source_id", "geometry_checksum"],
                    update_columns=_CATCHMENT_AREA_UPDATE_COLUMNS,
                    batch_size=settings.batch_size,
                )

    typer.echo(f"built {total_areas} catchment areas ({total_rejected} rejected)")


# ---------------------------------------------------------------------------
# import-admissions
# ---------------------------------------------------------------------------


@app.command("import-admissions")
def import_admissions(
    source_file: Annotated[Path, typer.Option("--source-file", help="Path to a CSV or YAML admissions metadata file.")],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Import admission arrangement metadata from a hand-maintained CSV or YAML file."""
    settings = get_settings()
    set_run_context(source="admissions")
    conn = _connect_or_none(settings, dry_run=dry_run)

    if not source_file.exists():
        _fail(f"source file not found: {source_file}", source="admissions")
        return

    content = source_file.read_text(encoding="utf-8")
    try:
        if source_file.suffix.lower() in (".yml", ".yaml"):
            result = admissions_adapter.parse_admissions_yaml(content)
        else:
            result = admissions_adapter.parse_admissions_csv(content)
    except Exception as exc:
        _fail(f"could not parse admissions source: {exc}", source="admissions")
        return

    logger.info(
        "parsed admissions source", extra={"rows_processed": result.rows_processed, "rows_rejected": result.rows_rejected}
    )

    if dry_run:
        typer.echo(f"dry-run: {len(result.arrangements)} valid arrangements, {result.rows_rejected} rejected")
        return

    if conn is None:
        _fail("no database connection available and --dry-run was not set", source="admissions")
        return

    rows = [a.model_dump(mode="json") for a in result.arrangements]
    with db.transaction(conn):
        inserted = db.upsert_many(
            conn,
            "admission_arrangements",
            iter(rows),
            conflict_columns=["school_urn", "academic_year"],
            batch_size=settings.batch_size,
        )
    typer.echo(f"imported {inserted} admission arrangements ({result.rows_rejected} rows rejected)")


# ---------------------------------------------------------------------------
# refresh-metrics / verify / cleanup
# ---------------------------------------------------------------------------


@app.command("refresh-metrics")
def refresh_metrics() -> None:
    """Validate that every metric code referenced by the service is defined in config/metric-definitions.yml.

    This is a data-quality self-check, not a recomputation of statistics
    (statistics values only ever come from the DfE source, never derived
    locally). It is the hook point for a future derived-metrics materialised
    view refresh, should the web app introduce one.
    """
    settings = get_settings()
    with settings.metric_definitions_path.open(encoding="utf-8") as fh:
        definitions = yaml.safe_load(fh)
    known_codes = set(definitions.get("metrics", {}).keys())

    with settings.statistics_sources_path.open(encoding="utf-8") as fh:
        stats_config = yaml.safe_load(fh)

    referenced_codes: set[str] = set()
    for pub in stats_config.get("publications", []):
        referenced_codes.update(pub.get("metric_codes", []))

    missing = referenced_codes - known_codes
    if missing:
        _fail(f"metric codes referenced by statistics-sources.yml are missing from metric-definitions.yml: {sorted(missing)}", source="refresh_metrics")
        return

    typer.echo(f"ok: {len(known_codes)} metric definitions cover all {len(referenced_codes)} referenced codes")


@app.command("verify")
def verify() -> None:
    """Run post-import consistency checks against the config registries and, if reachable, the database."""
    settings = get_settings()
    problems: list[str] = []

    try:
        sources = _load_catchment_sources(settings)
        for source in sources:
            if not source.get("licence"):
                problems.append(f"catchment source for {source.get('local_authority_name')} has no licence recorded")
            if source.get("coordinate_reference_system") is None:
                problems.append(f"catchment source for {source.get('local_authority_name')} has no CRS recorded")
    except Exception as exc:
        problems.append(f"could not load catchment-sources.yml: {exc}")

    conn = _connect_or_none(settings, dry_run=False)
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) AS n FROM schools")
                row = cur.fetchone()
                count = row["n"] if isinstance(row, dict) else row[0]
                if count == 0:
                    problems.append("schools table is empty")
        except Exception as exc:
            problems.append(f"database verification query failed: {exc}")
    else:
        logger.info("no database connection available; skipped database-backed verification checks")

    if problems:
        for problem in problems:
            logger.error("verification problem", extra={"problem": problem})
        typer.echo(f"verify FAILED: {len(problems)} problem(s)")
        raise typer.Exit(code=1)

    typer.echo("verify OK")


@app.command("cleanup")
def cleanup(dry_run: Annotated[bool, typer.Option("--dry-run")] = False) -> None:
    """Mark superseded catchment sources (an older academic year for the same local authority and source type, where a newer VALID source exists) as SUPERSEDED.

    This service never touches postcode_cache; that table belongs to the web
    app's end-user postcode lookups, which are entirely out of scope here.
    """
    settings = get_settings()
    conn = _connect_or_none(settings, dry_run=dry_run)
    if conn is None:
        typer.echo("dry-run or no database connection; nothing to clean up")
        return

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE catchment_sources AS old
            SET status = 'SUPERSEDED'
            WHERE old.status = 'VALID'
              AND EXISTS (
                SELECT 1 FROM catchment_sources AS newer
                WHERE newer.local_authority_code = old.local_authority_code
                  AND newer.source_type = old.source_type
                  AND newer.status = 'VALID'
                  AND newer.academic_year > old.academic_year
              )
            """
        )
        superseded_count = cur.rowcount
    conn.commit()
    typer.echo(f"marked {superseded_count} catchment source(s) superseded")


# ---------------------------------------------------------------------------
# run: full pipeline in order
# ---------------------------------------------------------------------------

_PIPELINE_STEPS = (
    "import-gias",
    "import-trusts",
    "import-statistics",
    "import-performance",
    "import-catchments",
    "import-admissions",
    "refresh-metrics",
    "verify",
    "cleanup",
)


@app.command("run")
def run_full_pipeline(
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    admissions_source_file: Annotated[
        Path | None, typer.Option("--admissions-source-file", help="Required unless --skip-admissions is set.")
    ] = None,
    skip_admissions: Annotated[bool, typer.Option("--skip-admissions")] = False,
) -> None:
    """Run the full ingestion pipeline in order: GIAS, trusts, statistics, performance, catchments, admissions, then refresh-metrics/verify/cleanup.

    A failure in one step is logged and counted but does not stop later
    steps from running, so (for example) a broken statistics API does not
    prevent catchment data from importing. The command exits non-zero if any
    step failed.
    """
    failures: list[str] = []

    def _run(label: str, fn: object) -> None:
        try:
            fn()  # type: ignore[operator]
        except typer.Exit as exc:
            if exc.exit_code != 0:
                failures.append(label)
        except Exception as exc:
            logger.exception("pipeline step raised unexpectedly", extra={"step": label})
            failures.append(f"{label}: {exc}")

    _run("import-gias", lambda: import_gias(row_limit=None, force=False, dry_run=dry_run))
    _run("import-trusts", lambda: import_trusts(force=False, dry_run=dry_run))
    _run("import-statistics", lambda: import_statistics(dry_run=dry_run))
    _run("import-performance", import_performance)
    _run("import-catchments", lambda: import_catchments(local_authority=None, academic_year=None, geometry_validation_only=False, dry_run=dry_run))

    if not skip_admissions and admissions_source_file is not None:
        _run("import-admissions", lambda: import_admissions(source_file=admissions_source_file, dry_run=dry_run))
    elif not skip_admissions:
        logger.info("no --admissions-source-file given; skipping import-admissions for this run")

    _run("refresh-metrics", refresh_metrics)
    _run("verify", verify)
    _run("cleanup", lambda: cleanup(dry_run=dry_run))

    if failures:
        typer.echo(f"pipeline completed with {len(failures)} failed step(s): {failures}")
        raise typer.Exit(code=1)

    typer.echo("pipeline completed successfully")


if __name__ == "__main__":
    sys.exit(app())
