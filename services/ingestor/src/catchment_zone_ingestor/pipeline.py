"""Pipeline orchestration: wraps each adapter call in an IngestionRun record.

Every import command in cli.py goes through one of the functions here, which:
starts an ingestion_runs row, calls the relevant adapter with tenacity retries
already applied at the HTTP layer inside the adapter, counts rows processed /
inserted / updated / rejected, and writes a final SUCCEEDED, FAILED or
SKIPPED_UNCHANGED status. A failure in one adapter never leaves a run stuck in
RUNNING: the surrounding try/except always reaches the final status update,
using FAILED with the exception summary if anything raised.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from catchment_zone_ingestor.db import ConnectionLike, upsert_many
from catchment_zone_ingestor.models import IngestionStatus

logger = logging.getLogger(__name__)


@dataclass
class RunCounts:
    rows_processed: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_rejected: int = 0
    geometry_records: int = 0
    metrics_records: int = 0


class IngestionOutcome:
    """Result of a single pipeline step, returned to the CLI so it can decide
    the process exit code."""

    def __init__(self, source: str, status: IngestionStatus, counts: RunCounts, error_summary: str | None = None):
        self.source = source
        self.status = status
        self.counts = counts
        self.error_summary = error_summary

    @property
    def succeeded(self) -> bool:
        return self.status in (IngestionStatus.SUCCEEDED, IngestionStatus.SKIPPED_UNCHANGED)


def create_ingestion_run(conn: ConnectionLike, source: str, source_date: datetime | None = None) -> str:
    """Insert a new ingestion_runs row in RUNNING status and return its id."""
    run_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_runs (id, source, source_date, status, started_at)
            VALUES (%(id)s, %(source)s, %(source_date)s, %(status)s, %(started_at)s)
            """,
            {
                "id": run_id,
                "source": source,
                "source_date": source_date,
                "status": IngestionStatus.RUNNING.value,
                "started_at": datetime.now(UTC),
            },
        )
    return run_id


def complete_ingestion_run(
    conn: ConnectionLike,
    run_id: str,
    status: IngestionStatus,
    counts: RunCounts,
    started_at_monotonic: float,
    error_summary: str | None = None,
    git_sha: str | None = None,
    workflow_run_url: str | None = None,
) -> None:
    """Update an ingestion_runs row with its final status and counts."""
    duration_seconds = time.monotonic() - started_at_monotonic
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingestion_runs
            SET status = %(status)s,
                rows_processed = %(rows_processed)s,
                rows_inserted = %(rows_inserted)s,
                rows_updated = %(rows_updated)s,
                rows_rejected = %(rows_rejected)s,
                geometry_records = %(geometry_records)s,
                metrics_records = %(metrics_records)s,
                duration_seconds = %(duration_seconds)s,
                error_summary = %(error_summary)s,
                git_sha = %(git_sha)s,
                workflow_run_url = %(workflow_run_url)s,
                finished_at = %(finished_at)s
            WHERE id = %(id)s
            """,
            {
                "id": run_id,
                "status": status.value,
                "rows_processed": counts.rows_processed,
                "rows_inserted": counts.rows_inserted,
                "rows_updated": counts.rows_updated,
                "rows_rejected": counts.rows_rejected,
                "geometry_records": counts.geometry_records,
                "metrics_records": counts.metrics_records,
                "duration_seconds": duration_seconds,
                "error_summary": error_summary,
                "git_sha": git_sha,
                "workflow_run_url": workflow_run_url,
                "finished_at": datetime.now(UTC),
            },
        )


def get_last_successful_checksum(conn: ConnectionLike, source: str) -> str | None:
    """Return the checksum recorded on the most recent SUCCEEDED run for this
    source, or None if there is no prior successful run. Used to decide
    whether an unchanged source file should be skipped this run.

    The checksum itself is stored in error_summary-adjacent metadata via the
    source-specific tables (e.g. catchment_sources.checksum); for sources
    without their own checksum column (like the GIAS extract), callers should
    pass a source string that embeds the checksum lookup table they use. This
    generic helper covers the common "did this source's IngestionRun already
    succeed with an identical checksum" question by checking error_summary,
    where adapters that have no dedicated checksum column record it in the
    format 'checksum:<sha256>' on success for exactly this purpose.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT error_summary FROM ingestion_runs
            WHERE source = %(source)s AND status = %(status)s
            ORDER BY started_at DESC
            LIMIT 1
            """,
            {"source": source, "status": IngestionStatus.SUCCEEDED.value},
        )
        row = cur.fetchone()
    if not row:
        return None
    raw_summary = row.get("error_summary") if isinstance(row, dict) else row[0]
    summary = str(raw_summary) if raw_summary is not None else None
    if summary and summary.startswith("checksum:"):
        return summary.removeprefix("checksum:")
    return None


def run_step(
    conn: ConnectionLike | None,
    source: str,
    step: Any,
    dry_run: bool,
) -> IngestionOutcome:
    """Run one pipeline step (a zero-argument callable returning RunCounts),
    wrapping it in an IngestionRun record. In dry-run mode, or when no
    connection is supplied, no ingestion_runs row is written; the step itself
    is still expected to honour dry_run by skipping database writes.
    """
    started_monotonic = time.monotonic()
    run_id: str | None = None
    if conn is not None and not dry_run:
        run_id = create_ingestion_run(conn, source)

    try:
        counts, status, checksum = step()
    except Exception as exc:
        logger.exception("ingestion step failed", extra={"source": source})
        counts = RunCounts()
        if conn is not None and not dry_run and run_id is not None:
            complete_ingestion_run(conn, run_id, IngestionStatus.FAILED, counts, started_monotonic, error_summary=str(exc))
        return IngestionOutcome(source, IngestionStatus.FAILED, counts, error_summary=str(exc))

    error_summary = f"checksum:{checksum}" if checksum else None
    if conn is not None and not dry_run and run_id is not None:
        complete_ingestion_run(conn, run_id, status, counts, started_monotonic, error_summary=error_summary)

    return IngestionOutcome(source, status, counts, error_summary=error_summary)


def upsert_schools(conn: ConnectionLike, rows: list[dict[str, Any]], batch_size: int) -> int:
    return upsert_many(conn, "schools", rows, conflict_columns=["urn"], batch_size=batch_size)


def upsert_academy_trusts(conn: ConnectionLike, rows: list[dict[str, Any]], batch_size: int) -> int:
    return upsert_many(conn, "academy_trusts", rows, conflict_columns=["trust_id"], batch_size=batch_size)


def upsert_school_metrics(conn: ConnectionLike, rows: list[dict[str, Any]], batch_size: int) -> int:
    return upsert_many(
        conn,
        "school_metrics",
        rows,
        conflict_columns=["school_urn", "metric_code", "academic_year"],
        batch_size=batch_size,
    )


def upsert_admission_arrangements(conn: ConnectionLike, rows: list[dict[str, Any]], batch_size: int) -> int:
    return upsert_many(
        conn,
        "admission_arrangements",
        rows,
        conflict_columns=["school_urn", "academic_year"],
        batch_size=batch_size,
    )
