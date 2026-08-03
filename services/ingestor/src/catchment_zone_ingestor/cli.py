"""Typer CLI entrypoint for the catchment-zone ingestion service.

Each command wraps one pipeline step (or, for `run`, the whole sequence) and
exits non-zero on failure so a scheduled CI job can detect a failed run. All
commands log structured JSON via logging_setup.configure_logging.
"""

from __future__ import annotations

import hashlib
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, cast

import httpx
import psycopg
import typer
import yaml
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from catchment_zone_ingestor import db, pipeline
from catchment_zone_ingestor.adapters import admissions as admissions_adapter
from catchment_zone_ingestor.adapters import catchment_scores as catchment_scores_adapter
from catchment_zone_ingestor.adapters import catchments as catchments_adapter
from catchment_zone_ingestor.adapters import gias as gias_adapter
from catchment_zone_ingestor.adapters import scotland as scotland_adapter
from catchment_zone_ingestor.adapters import statistics as statistics_adapter
from catchment_zone_ingestor.adapters import wales as wales_adapter
from catchment_zone_ingestor.adapters import wales_performance as wales_performance_adapter
from catchment_zone_ingestor.config import Settings, get_settings
from catchment_zone_ingestor.logging_setup import configure_logging, get_logger, set_run_context
from catchment_zone_ingestor.models import IngestionStatus

app = typer.Typer(
    name="ingestor",
    help="catchment-zone data ingestion service: GIAS, DfE statistics and local authority catchment imports.",
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
        headers={"User-Agent": "catchment-zone-ingestor/0.1 (public-data ingestion; contact via repo)"},
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


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(psycopg.errors.SerializationFailure),
)
def _upsert_batch_with_retry(
    conn: db.ConnectionLike,
    table: str,
    batch: list[dict[str, Any]],
    conflict_columns: list[str],
) -> int:
    """Upserts one batch inside its own short transaction, retrying just
    that batch from scratch on a CockroachDB SERIALIZABLE retry error
    (SQLSTATE 40001). Safe to retry since every write here is an
    idempotent upsert (ON CONFLICT DO UPDATE)."""
    with db.transaction(conn):
        return db.upsert_batch(conn, table, batch, conflict_columns=conflict_columns)


def _upsert_many_with_retry(
    conn: db.ConnectionLike,
    table: str,
    rows: list[dict[str, Any]],
    conflict_columns: list[str],
    batch_size: int,
) -> int:
    """Upserts a large row set as many small, independently-committed and
    independently-retried transactions, one per batch, rather than a
    single transaction spanning the whole data set.

    Verified live: wrapping an entire ~98,000-row upsert (about 99
    batches of 1000) in one transaction reliably hit a CockroachDB
    SERIALIZABLE retry error on COMMIT, even with a whole-transaction
    retry wrapper retried 3 times - the transaction is simply too
    long-running/many-statement for serializable isolation to commit
    reliably at this size on this cluster. Trades all-or-nothing
    atomicity per data set for reliability at this data volume: a run
    that fails partway through leaves the batches committed so far in
    place, and a re-run safely fills in the rest (every write is an
    idempotent upsert)."""
    total = 0
    for batch in db.batched(rows, batch_size=batch_size):
        total += _upsert_batch_with_retry(conn, table, batch, conflict_columns)
    return total


class _RunTracker:
    """Mutable state a command fills in inside a `with _tracked_run(...)`
    block: row counts for the ingestion_runs record, and optionally a
    source checksum (GIAS extracts) so a future run's --force-less
    checksum-skip check (get_last_successful_checksum) has something real
    to compare against - previously impossible, since no run was ever
    recorded for it to find."""

    def __init__(self) -> None:
        self.counts = pipeline.RunCounts()
        self.checksum: str | None = None


@contextmanager
def _tracked_run(conn: db.ConnectionLike | None, source: str, dry_run: bool) -> Iterator[_RunTracker]:
    """Records an ingestion_runs row around a command's real work, so
    /status's "recent ingestion runs" reflects what actually happened.

    pipeline.py already had a complete create_ingestion_run/
    complete_ingestion_run implementation; nothing in cli.py ever called
    it, so ingestion_runs was empty after every real import this project
    has ever run (found while writing the pilot calibration report).
    Deliberately a thin wrapper rather than a rewrite, since pipeline.py's
    functions were already correct, just unused.

    Yields a _RunTracker the caller fills in as it goes. On dry-run or
    when no connection is available, tracking is skipped entirely (there
    is nothing to record). Each write commits immediately and
    independently of whatever transaction the caller's own work uses, so
    a rollback in the caller's data-writing transaction never also
    discards the run record explaining what happened.
    """
    tracker = _RunTracker()
    if conn is None or dry_run:
        yield tracker
        return

    run_id = pipeline.create_ingestion_run(conn, source)
    conn.commit()
    started_monotonic = time.monotonic()
    try:
        yield tracker
    except Exception as exc:
        pipeline.complete_ingestion_run(
            conn, run_id, IngestionStatus.FAILED, tracker.counts, started_monotonic, error_summary=str(exc)[:1000]
        )
        conn.commit()
        raise
    else:
        error_summary = f"checksum:{tracker.checksum}" if tracker.checksum else None
        pipeline.complete_ingestion_run(
            conn, run_id, IngestionStatus.SUCCEEDED, tracker.counts, started_monotonic, error_summary=error_summary
        )
        conn.commit()


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
            from catchment_zone_ingestor.pipeline import get_last_successful_checksum

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

        with _tracked_run(conn, "gias_establishments", dry_run) as tracker:
            # local_authorities first: schools.local_authority_code is a
            # foreign key to it, and this extract is the only source of
            # local authority identity this service has, so a school row
            # referencing a not-yet-seen LA code would otherwise fail that
            # constraint.
            la_rows = [la.model_dump(mode="json") for la in result.local_authorities]
            rows = [s.model_dump(mode="json") for s in result.schools]
            with db.transaction(conn):
                la_upserted = db.upsert_many(conn, "local_authorities", iter(la_rows), conflict_columns=["code"])
                inserted = db.upsert_many(
                    conn, "schools", iter(rows), conflict_columns=["urn"], batch_size=settings.batch_size
                )
            tracker.counts.rows_processed = result.rows_processed
            tracker.counts.rows_inserted = inserted
            tracker.counts.rows_rejected = result.rows_rejected
            tracker.checksum = checksum

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
            from catchment_zone_ingestor.pipeline import get_last_successful_checksum

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
        with _tracked_run(conn, "gias_trusts", dry_run) as tracker:
            with db.transaction(conn):
                inserted = db.upsert_many(
                    conn, "academy_trusts", iter(rows), conflict_columns=["trust_id"], batch_size=settings.batch_size
                )
            tracker.counts.rows_processed = result.rows_processed
            tracker.counts.rows_inserted = inserted
            tracker.counts.rows_rejected = result.rows_rejected
            tracker.checksum = checksum
        typer.echo(f"imported {inserted} trusts ({result.rows_rejected} rows rejected)")
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(f"trust import failed: {exc}", source="gias_trusts")


# ---------------------------------------------------------------------------
# import-scotland
# ---------------------------------------------------------------------------


@app.command("import-scotland")
def import_scotland(
    row_limit: Annotated[int | None, typer.Option(help="Only process the first N features (testing/debugging).")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Fetch and validate only; do not write to the database.")] = False,
) -> None:
    """Import Scotland's school register from the live ScottishSchoolRoll ArcGIS service.

    No checksum-skip here (unlike import-gias): the ArcGIS service has no
    published extract-date/version field to compare against, so every run
    re-fetches and re-upserts the current 2,483 rows.
    """
    settings = get_settings()
    set_run_context(source="scotland_schools")
    conn = _connect_or_none(settings, dry_run=dry_run)

    try:
        with _http_client(settings) as client:
            features = scotland_adapter.fetch_scotland_schools(client)

        result = scotland_adapter.parse_scotland_schools(features, row_limit=row_limit)
        logger.info(
            "parsed Scotland school register",
            extra={"rows_processed": result.rows_processed, "rows_rejected": result.rows_rejected},
        )
        if result.rejection_samples:
            logger.warning("sample rejected Scotland rows", extra={"samples": result.rejection_samples})

        if dry_run:
            typer.echo(
                f"dry-run: {len(result.schools)} valid schools, "
                f"{len(result.local_authorities)} local authorities, {result.rows_rejected} rejected rows"
            )
            return

        if conn is None:
            _fail("no database connection available and --dry-run was not set", source="scotland_schools")
            return

        la_rows = [la.model_dump(mode="json") for la in result.local_authorities]
        rows = [s.model_dump(mode="json") for s in result.schools]
        with _tracked_run(conn, "scotland_schools", dry_run) as tracker:
            with db.transaction(conn):
                la_upserted = db.upsert_many(conn, "local_authorities", iter(la_rows), conflict_columns=["code"])
                inserted = db.upsert_many(
                    conn, "schools", iter(rows), conflict_columns=["urn"], batch_size=settings.batch_size
                )
            tracker.counts.rows_processed = result.rows_processed
            tracker.counts.rows_inserted = inserted
            tracker.counts.rows_rejected = result.rows_rejected

        logger.info(
            "imported Scotland schools", extra={"rows_upserted": inserted, "local_authorities_upserted": la_upserted}
        )
        typer.echo(f"imported {inserted} schools, {la_upserted} local authorities ({result.rows_rejected} rows rejected)")
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(f"Scotland import failed: {exc}", source="scotland_schools")


# ---------------------------------------------------------------------------
# import-wales
# ---------------------------------------------------------------------------


@app.command("import-wales")
def import_wales(
    row_limit: Annotated[int | None, typer.Option(help="Only process the first N features (testing/debugging).")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Fetch and validate only; do not write to the database.")] = False,
) -> None:
    """Import Wales's school register from the live DataMapWales WFS layer.

    No checksum-skip here (unlike import-gias): the WFS layer has no
    published extract-date/version field to compare against, so every run
    re-fetches and re-upserts the current ~1,440 rows.
    """
    settings = get_settings()
    set_run_context(source="wales_schools")
    conn = _connect_or_none(settings, dry_run=dry_run)

    try:
        with _http_client(settings) as client:
            features = wales_adapter.fetch_wales_schools(client)

        result = wales_adapter.parse_wales_schools(features, row_limit=row_limit)
        logger.info(
            "parsed Wales school register",
            extra={"rows_processed": result.rows_processed, "rows_rejected": result.rows_rejected},
        )
        if result.rejection_samples:
            logger.warning("sample rejected Wales rows", extra={"samples": result.rejection_samples})

        if dry_run:
            typer.echo(
                f"dry-run: {len(result.schools)} valid schools, "
                f"{len(result.local_authorities)} local authorities, {result.rows_rejected} rejected rows"
            )
            return

        if conn is None:
            _fail("no database connection available and --dry-run was not set", source="wales_schools")
            return

        la_rows = [la.model_dump(mode="json") for la in result.local_authorities]
        rows = [s.model_dump(mode="json") for s in result.schools]
        with _tracked_run(conn, "wales_schools", dry_run) as tracker:
            with db.transaction(conn):
                la_upserted = db.upsert_many(conn, "local_authorities", iter(la_rows), conflict_columns=["code"])
                inserted = db.upsert_many(
                    conn, "schools", iter(rows), conflict_columns=["urn"], batch_size=settings.batch_size
                )
            tracker.counts.rows_processed = result.rows_processed
            tracker.counts.rows_inserted = inserted
            tracker.counts.rows_rejected = result.rows_rejected

        logger.info(
            "imported Wales schools", extra={"rows_upserted": inserted, "local_authorities_upserted": la_upserted}
        )
        typer.echo(f"imported {inserted} schools, {la_upserted} local authorities ({result.rows_rejected} rows rejected)")
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(f"Wales import failed: {exc}", source="wales_schools")


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
def import_performance(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Parse and validate only; do not write to the database.")] = False,
) -> None:
    """Import SchoolMetric rows for the school performance tables listed
    under performance_datasets in config/statistics-sources.yml (GCSE/
    key stage 4 and key stage 2 SATs results) - genuinely school-level
    data, unlike import-statistics's local-authority-level publications.
    """
    settings = get_settings()
    set_run_context(source="dfe_performance")
    conn = _connect_or_none(settings, dry_run=dry_run)

    config = _load_statistics_config(settings)
    base_url = str(config["api"]["base_url"])
    datasets: list[dict[str, Any]] = config.get("performance_datasets", [])
    if not datasets:
        typer.echo("no performance_datasets configured in config/statistics-sources.yml; skipped")
        return

    # SchoolMetric.school_urn is a real foreign key to schools.urn; a
    # performance-table row for a URN not (yet) in schools would fail the
    # whole upsert batch it lands in rather than just that one row, so
    # known URNs are checked up front and unknown ones are skipped and
    # logged individually instead, consistent with every other adapter's
    # per-row tolerance.
    known_urns: set[str] = set()
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute("SELECT urn FROM schools")
            known_urns = {row["urn"] for row in cur.fetchall()}

    total_upserted = 0
    total_skipped_unknown_urn = 0
    total_failed_datasets = 0

    with _http_client(settings) as client:
        for dataset_config in datasets:
            slug = str(dataset_config["publication_slug"])
            title = str(dataset_config["dataset_title"])
            try:
                release = statistics_adapter.find_dataset_id_by_title(client, base_url, slug, title)
                rows = statistics_adapter.fetch_dataset_csv_rows(client, base_url, release.dataset_id)
                metrics = list(statistics_adapter.map_performance_rows_to_metrics(rows, dataset_config, release))
            except Exception as exc:
                total_failed_datasets += 1
                logger.warning(
                    "could not import performance dataset",
                    extra={"publication_slug": slug, "dataset_title": title, "error": str(exc)},
                )
                continue

            if known_urns:
                before = len(metrics)
                metrics = [m for m in metrics if m.school_urn in known_urns]
                total_skipped_unknown_urn += before - len(metrics)

            logger.info(
                "parsed performance dataset",
                extra={"publication_slug": slug, "dataset_title": title, "metric_rows": len(metrics)},
            )

            if dry_run or conn is None:
                typer.echo(f"dry-run: {title!r} -> {len(metrics)} metric rows")
                continue

            metric_rows = [m.model_dump(mode="json") for m in metrics]
            with _tracked_run(conn, f"dfe_performance:{slug}", dry_run) as tracker:
                upserted = _upsert_many_with_retry(
                    conn,
                    "school_metrics",
                    metric_rows,
                    conflict_columns=["school_urn", "metric_code", "academic_year"],
                    batch_size=settings.batch_size,
                )
                tracker.counts.rows_processed = len(metrics)
                tracker.counts.rows_inserted = upserted
            total_upserted += upserted

    if total_failed_datasets == len(datasets):
        _fail("could not import any configured performance dataset", source="dfe_performance")
        return

    typer.echo(
        f"imported {total_upserted} school metric rows "
        f"({total_skipped_unknown_urn} skipped for unknown school_urn, "
        f"{total_failed_datasets} dataset(s) failed)"
    )


# ---------------------------------------------------------------------------
# import-wales-performance
# ---------------------------------------------------------------------------


@app.command("import-wales-performance")
def import_wales_performance(
    row_limit: Annotated[int | None, typer.Option(help="Only fetch the first N schools (testing/debugging).")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Fetch and parse only; do not write to the database.")] = False,
) -> None:
    """Import key stage 4 SchoolMetric rows for Welsh secondary schools from
    mylocalschool.gov.wales (no bulk API exists; one page per school - see
    wales_performance.py's module docstring for why this source and
    fetch shape were chosen).
    """
    settings = get_settings()
    set_run_context(source="wales_performance")
    # Unlike every other command's dry_run gating, a connection is needed
    # here even in dry-run mode: it is the only way to list which Welsh
    # secondary schools to fetch (there is no external "source list" to
    # read from first the way GIAS/EES-backed imports have). dry_run only
    # skips the write at the end.
    conn = _connect_or_none(settings, dry_run=False)
    if conn is None:
        _fail("a database connection is required to list Welsh secondary schools", source="wales_performance")
        return

    with conn.cursor() as cur:
        cur.execute(
            "SELECT urn FROM schools WHERE nation = 'WALES' AND phase_name ILIKE %(pattern)s ORDER BY urn",
            {"pattern": "%secondary%"},
        )
        urns = [row["urn"] for row in cur.fetchall()]
    if row_limit is not None:
        urns = urns[:row_limit]

    with _http_client(settings) as client:
        fetch_result = wales_performance_adapter.fetch_all_schools_performance(client, urns)

    logger.info(
        "fetched Wales school performance pages",
        extra={
            "schools_fetched": fetch_result.schools_fetched,
            "schools_failed": fetch_result.schools_failed,
            "metric_rows": len(fetch_result.metrics),
        },
    )
    if fetch_result.failure_samples:
        logger.warning("sample failed Wales school performance fetches", extra={"samples": fetch_result.failure_samples})

    if dry_run:
        typer.echo(
            f"dry-run: {fetch_result.schools_fetched} schools fetched, "
            f"{len(fetch_result.metrics)} metric rows, {fetch_result.schools_failed} schools failed"
        )
        return

    metric_rows = [m.model_dump(mode="json") for m in fetch_result.metrics]
    with _tracked_run(conn, "wales_performance", dry_run) as tracker:
        upserted = _upsert_many_with_retry(
            conn,
            "school_metrics",
            metric_rows,
            conflict_columns=["school_urn", "metric_code", "academic_year"],
            batch_size=settings.batch_size,
        )
        tracker.counts.rows_processed = len(fetch_result.metrics)
        tracker.counts.rows_inserted = upserted

    typer.echo(
        f"imported {upserted} school metric rows from {fetch_result.schools_fetched} schools "
        f"({fetch_result.schools_failed} schools failed)"
    )


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
                if source.get("format") == "wfs_geojson":
                    type_name = str(source["wfs_type_name"])
                    query_result = catchments_adapter.query_all_wfs_features(client, feature_url, type_name)
                elif source.get("format") == "shapefile_zip":
                    query_result = catchments_adapter.download_shapefile_zip_features(client, feature_url)
                else:
                    arcgis_where = str(source["arcgis_where"]) if source.get("arcgis_where") else "1=1"
                    query_result = catchments_adapter.query_all_features(client, feature_url, where=arcgis_where)
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
                name_field_candidates=[
                    "SCHOOL_NAME",
                    "NAME",
                    "name",
                    "SchoolName",
                    # Edinburgh's four catchment layers (primary/secondary x
                    # non-denominational/Roman Catholic) use EST_NAME
                    # consistently, unlike SCHOOL_NAM/SCHOOL/SCH_NAME which
                    # vary per layer; carrying the school's actual name
                    # (verified live: "Abbeyhill Primary School" etc.)
                    # unlike Sheffield/Aberdeen's zone-name-only sources.
                    "EST_NAME",
                    # Fife's four catchment layers use this truncated
                    # (10-char, shapefile-derived) field name - not the
                    # same as "SCHOOL_NAME" above, verified live.
                    "SCHOOL_NAM",
                    # Highland's secondary layer and Dundee's four layers
                    # use these field names respectively, verified live.
                    "SECONDARY",
                    "School",
                    # South Ayrshire's four layers each use their own
                    # lowercase field name, verified live (real school
                    # names, e.g. "Sacred Heart", "Marr College").
                    "ndprimary",
                    "rcprimary",
                    "ndsecondar",
                    "schoolname",
                    # Angus's WFS layers (XMap Cloud, not ArcGIS) use this.
                    "school_name",
                    # Aberdeenshire's shapefile (10-char dbf field limit,
                    # lowercase) uses this - distinct from Fife's uppercase
                    # SCHOOL_NAM above, verified live.
                    "school_nam",
                    # Stirling's ArcGIS Online layers use this, verified live.
                    "School_Name",
                    # Argyll and Bute's Open_Data catchment layers use this
                    # short field name (real school names without a
                    # "Primary/Secondary School" suffix, e.g. "Tayvallich"),
                    # verified live.
                    "NM",
                    # Moray's ArcGIS layers use this, verified live.
                    "SCHOOL",
                ],
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
            run_source = f"catchments:{source['local_authority_code']}:{source['source_type']}"
            with _tracked_run(conn, run_source, dry_run) as tracker:
                with db.transaction(conn):
                    db.upsert_many(
                        conn,
                        "catchment_sources",
                        iter([source_row]),
                        conflict_columns=["local_authority_code", "academic_year", "source_type"],
                        update_columns=[
                            c
                            for c in source_row
                            if c not in ("id", "local_authority_code", "academic_year", "source_type")
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
                    # Real, verified catchment data now exists for this local
                    # authority; reflect that so /local-authorities doesn't keep
                    # showing "not available" for one that actually has coverage
                    # (found live: this had never been set anywhere, so Sheffield
                    # itself showed as NOT_AVAILABLE despite having 127 areas).
                    # Only upgrades from the NOT_AVAILABLE default, never
                    # downgrades a status set some other way (e.g. by hand).
                    if build_result.areas:
                        with conn.cursor() as cur:
                            cur.execute(
                                "UPDATE local_authorities SET catchment_coverage_status = 'PILOT', "
                                "updated_at = now() WHERE code = %(code)s AND catchment_coverage_status = 'NOT_AVAILABLE'",
                                {"code": source["local_authority_code"]},
                            )
                tracker.counts.rows_processed = len(query_result.features)
                tracker.counts.geometry_records = len(build_result.areas)
                tracker.counts.rows_rejected = build_result.rejected_count

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
# refresh-catchment-scores
# ---------------------------------------------------------------------------


@app.command("refresh-catchment-scores")
def refresh_catchment_scores(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Compute only; do not write to the database.")] = False,
) -> None:
    """Recomputes every catchment area's performance_percentile: the
    served school's percentile rank on whichever metric applies to the
    area's phase and nation, averaged across every school whose point
    falls inside the polygon (see catchment_scores.py for the full
    method). Depends on both import-catchments and the performance-
    metric imports having already run; re-run this whenever either
    changes, not just once.
    """
    settings = get_settings()
    set_run_context(source="catchment_scores")
    conn = _connect_or_none(settings, dry_run=False)
    if conn is None:
        _fail("a database connection is required to compute catchment scores", source="catchment_scores")
        return

    schools = catchment_scores_adapter.load_schools_with_coordinates(conn)
    areas = catchment_scores_adapter.load_catchment_areas(conn)

    metric_codes = catchment_scores_adapter.all_configured_metric_codes()
    percentiles_by_metric = {
        code: catchment_scores_adapter.compute_percentiles(catchment_scores_adapter.load_latest_metric_values(conn, code))
        for code in metric_codes
    }

    scores = catchment_scores_adapter.compute_catchment_scores(areas, schools, percentiles_by_metric)
    scored_count = sum(1 for s in scores if s.performance_percentile is not None)

    logger.info(
        "computed catchment scores",
        extra={"total_areas": len(scores), "scored_areas": scored_count},
    )

    if dry_run:
        typer.echo(f"dry-run: {scored_count} of {len(scores)} catchment areas would be scored")
        return

    updated = catchment_scores_adapter.write_catchment_scores(conn, scores, settings.batch_size)
    typer.echo(f"scored {scored_count} of {updated} catchment areas")


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
    for dataset in stats_config.get("performance_datasets", []):
        referenced_codes.update(metric["metric_code"] for metric in dataset.get("metrics", []))
    # Wales's performance metric codes are not config-driven (mylocalschool.gov.wales
    # has no source config the way EES-backed datasets do), so they are
    # checked directly against the adapter's own name-to-code mapping.
    referenced_codes.update(wales_performance_adapter.METRIC_NAME_TO_CODE.values())

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
    "import-wales-performance",
    "import-catchments",
    "import-admissions",
    "refresh-catchment-scores",
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
    _run("import-performance", lambda: import_performance(dry_run=dry_run))
    _run("import-wales-performance", lambda: import_wales_performance(row_limit=None, dry_run=dry_run))
    _run("import-catchments", lambda: import_catchments(local_authority=None, academic_year=None, geometry_validation_only=False, dry_run=dry_run))

    if not skip_admissions and admissions_source_file is not None:
        _run("import-admissions", lambda: import_admissions(source_file=admissions_source_file, dry_run=dry_run))
    elif not skip_admissions:
        logger.info("no --admissions-source-file given; skipping import-admissions for this run")

    _run("refresh-catchment-scores", lambda: refresh_catchment_scores(dry_run=dry_run))
    _run("refresh-metrics", refresh_metrics)
    _run("verify", verify)
    _run("cleanup", lambda: cleanup(dry_run=dry_run))

    if failures:
        typer.echo(f"pipeline completed with {len(failures)} failed step(s): {failures}")
        raise typer.Exit(code=1)

    typer.echo("pipeline completed successfully")


if __name__ == "__main__":
    sys.exit(app())
