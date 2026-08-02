"""Tests for db.upsert_batch's generated SQL.

Uses a lightweight fake connection/cursor rather than a live database, per
this service's "no live database in tests" constraint (see db.py's
ConnectionLike Protocol).
"""

from __future__ import annotations

from catchment_zone_ingestor.db import upsert_batch


class _FakeCursor:
    def __init__(self, sink: list[tuple[str, list[dict[str, object]]]]) -> None:
        self._sink = sink

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def executemany(self, sql: str, rows: list[dict[str, object]]) -> None:
        self._sink.append((sql, rows))


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, list[dict[str, object]]]] = []

    def cursor(self, **kwargs: object) -> _FakeCursor:
        return _FakeCursor(self.executed)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def test_upsert_batch_sets_updated_at_on_insert() -> None:
    """updated_at has no SQL DEFAULT (mirrors Prisma's @updatedAt, which
    Prisma Client normally sets on every write); a raw upsert must supply it
    explicitly or every first insert into an affected table fails NOT NULL."""
    conn = _FakeConnection()
    rows = [{"urn": "900001", "school_name": "Test School"}]

    upsert_batch(conn, "schools", rows, conflict_columns=["urn"])

    assert len(conn.executed) == 1
    sql, _ = conn.executed[0]
    assert "updated_at" in sql
    assert "now()" in sql


def test_upsert_batch_refreshes_updated_at_on_conflict() -> None:
    conn = _FakeConnection()
    rows = [{"urn": "900001", "school_name": "Test School"}]

    upsert_batch(conn, "schools", rows, conflict_columns=["urn"])

    sql, _ = conn.executed[0]
    assert "DO UPDATE SET" in sql
    assert "updated_at = now()" in sql


def test_upsert_batch_returns_no_rows_for_empty_input() -> None:
    conn = _FakeConnection()
    assert upsert_batch(conn, "schools", [], conflict_columns=["urn"]) == 0
    assert conn.executed == []
