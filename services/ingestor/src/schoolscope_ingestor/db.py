"""Database access layer: psycopg3 connection helper and batch upsert helpers.

Every write path in this service goes through batch operations (executemany
with a fixed page size) rather than one INSERT per row, since national GIAS
extracts run to 30,000+ rows and per-row round trips would make a full import
impractically slow. Nothing here issues a raw string-interpolated SQL query;
all statements use psycopg parameter placeholders.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from contextlib import contextmanager
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

#: Default number of rows per executemany batch / COPY buffer flush.
DEFAULT_BATCH_SIZE = 1000


class ConnectionLike(Protocol):
    """The subset of a psycopg Connection this module relies on.

    Declared as a Protocol so tests can pass a lightweight fake connection
    instead of opening a real database, per the "no live database in tests"
    constraint on this service.
    """

    def cursor(self, **kwargs: Any) -> Any: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def connect(database_url: str) -> psycopg.Connection[Any]:
    """Open a new psycopg3 connection with dict-row results and autocommit off."""
    return psycopg.connect(database_url, row_factory=dict_row, autocommit=False)


@contextmanager
def transaction(conn: ConnectionLike) -> Any:
    """Commit on clean exit, roll back and re-raise on any exception."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def batched(rows: Iterable[dict[str, Any]], batch_size: int = DEFAULT_BATCH_SIZE) -> Iterable[list[dict[str, Any]]]:
    """Yield rows in fixed-size lists, the last one possibly shorter.

    A plain generator-based batcher, used everywhere a source is streamed
    (CSV rows, paginated API results, ArcGIS feature pages) so the full
    dataset is never materialised in memory at once.
    """
    batch: list[dict[str, Any]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def upsert_batch(
    conn: ConnectionLike,
    table: str,
    rows: Sequence[dict[str, Any]],
    conflict_columns: Sequence[str],
    update_columns: Sequence[str] | None = None,
) -> int:
    """Upsert a batch of rows via a single executemany'd INSERT ... ON CONFLICT.

    All rows in a batch must share the same set of columns (the first row's
    keys define the statement's column list). Returns the number of rows
    submitted in the batch (psycopg's executemany does not reliably report
    per-row affected counts across all backends, so callers that need
    inserted-vs-updated counts should compare row counts before/after or use
    a RETURNING-based variant for smaller, high-value tables).

    update_columns defaults to every column except the conflict columns, i.e.
    a full upsert of the row.
    """
    if not rows:
        return 0

    columns = list(rows[0].keys())
    if update_columns is None:
        update_columns = [c for c in columns if c not in conflict_columns]

    column_list = ", ".join(columns)
    placeholder_list = ", ".join(f"%({c})s" for c in columns)
    conflict_list = ", ".join(conflict_columns)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_columns)

    if update_clause:
        on_conflict = f"ON CONFLICT ({conflict_list}) DO UPDATE SET {update_clause}"
    else:
        on_conflict = f"ON CONFLICT ({conflict_list}) DO NOTHING"

    sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholder_list}) {on_conflict}"

    with conn.cursor() as cur:
        cur.executemany(sql, rows)

    return len(rows)


def upsert_many(
    conn: ConnectionLike,
    table: str,
    rows: Iterable[dict[str, Any]],
    conflict_columns: Sequence[str],
    update_columns: Sequence[str] | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    """Upsert an arbitrarily large, streamed iterable of rows in batches.

    This is the entry point adapters should call: it handles batching
    internally so callers never need to build the full row list in memory.
    Returns the total number of rows submitted.
    """
    total = 0
    for batch in batched(rows, batch_size=batch_size):
        total += upsert_batch(conn, table, batch, conflict_columns, update_columns)
        logger.debug("upserted batch", extra={"table": table, "batch_rows": len(batch), "total_so_far": total})
    return total
