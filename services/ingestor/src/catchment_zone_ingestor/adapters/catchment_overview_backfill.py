"""One-time backfill of catchment_areas.overview_geometry_geojson for rows
that predate the column: new imports populate it directly (see
build_catchment_areas in catchments.py), so this only needs to run once per
existing row, not on a schedule.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import psycopg
from shapely.geometry import shape
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from catchment_zone_ingestor import db
from catchment_zone_ingestor.geometry import (
    OVERVIEW_SIMPLIFY_TOLERANCE_DEGREES,
    geometry_to_geojson_str,
    simplify_geometry,
)


@dataclass
class PendingOverviewRow:
    id: str
    geometry_geojson: str


def load_rows_missing_overview_geometry(
    conn: db.ConnectionLike, *, force: bool = False
) -> list[PendingOverviewRow]:
    """Uses the already-simplified geometry_geojson, not the full-precision
    geometry_geojson column, as input: it's already valid and topology-
    repaired from import time, and simplifying an already-simplified
    geometry further is both faster and produces an equivalent result at
    this coarser tolerance.

    force=True recomputes every row regardless of whether
    overview_geometry_geojson is already set - needed after a change to
    OVERVIEW_SIMPLIFY_TOLERANCE_DEGREES itself, when existing rows hold a
    value computed at the old tolerance."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, simplified_geometry_geojson FROM catchment_areas"
            if force
            else """
            SELECT id, simplified_geometry_geojson
            FROM catchment_areas
            WHERE overview_geometry_geojson IS NULL
            """
        )
        return [
            PendingOverviewRow(id=row["id"], geometry_geojson=row["simplified_geometry_geojson"])
            for row in cur.fetchall()
        ]


def compute_overview_geometry(geometry_geojson: str) -> str:
    geometry = shape(json.loads(geometry_geojson))
    overview = simplify_geometry(geometry, tolerance=OVERVIEW_SIMPLIFY_TOLERANCE_DEGREES)
    return geometry_to_geojson_str(overview)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(psycopg.errors.SerializationFailure),
)
def _write_batch_with_retry(conn: db.ConnectionLike, batch: list[dict[str, object]]) -> None:
    """Same per-batch-transaction retry pattern as catchment_scores.py's
    _write_batch_with_retry, for the same reason (CockroachDB SQLSTATE
    40001 SERIALIZABLE retry errors under concurrent writes)."""
    with db.transaction(conn), conn.cursor() as cur:
        cur.executemany(
            """
            UPDATE catchment_areas
            SET overview_geometry_geojson = %(overview_geometry_geojson)s,
                updated_at = now()
            WHERE id = %(id)s
            """,
            batch,
        )


def backfill_overview_geometry(
    conn: db.ConnectionLike, batch_size: int, *, force: bool = False
) -> int:
    rows = load_rows_missing_overview_geometry(conn, force=force)
    updates = [
        {"id": row.id, "overview_geometry_geojson": compute_overview_geometry(row.geometry_geojson)}
        for row in rows
    ]
    total = 0
    for batch in db.batched(updates, batch_size=batch_size):
        _write_batch_with_retry(conn, batch)
        total += len(batch)
    return total
