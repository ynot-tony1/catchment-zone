"""Tests for cli._resolve_catchment_source_id.

catchment_sources.id has no SQL-level DEFAULT (Prisma's @default(uuid()) is
client-side), so the ingestor must mint or reuse an id itself; a re-import
must reuse the existing row's id rather than minting a new one, or every
catchment_areas row already written against it would be orphaned.
"""

from __future__ import annotations

import uuid

from catchment_zone_ingestor.cli import _resolve_catchment_source_id

_SOURCE = {"local_authority_code": "373", "academic_year": "2025-2026", "source_type": "primary_catchment"}


class _FakeCursor:
    def __init__(self, existing_id: str | None) -> None:
        self._existing_id = existing_id

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: dict[str, object]) -> None:
        pass

    def fetchone(self) -> dict[str, str] | None:
        return {"id": self._existing_id} if self._existing_id else None


class _FakeConnection:
    def __init__(self, existing_id: str | None) -> None:
        self._existing_id = existing_id

    def cursor(self, **kwargs: object) -> _FakeCursor:
        return _FakeCursor(self._existing_id)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def test_reuses_existing_source_id_when_a_matching_row_exists() -> None:
    existing_id = str(uuid.uuid4())
    conn = _FakeConnection(existing_id)
    assert _resolve_catchment_source_id(conn, _SOURCE) == existing_id


def test_mints_a_fresh_id_when_no_matching_row_exists() -> None:
    conn = _FakeConnection(None)
    result = _resolve_catchment_source_id(conn, _SOURCE)
    assert uuid.UUID(result)


def test_mints_a_fresh_id_with_no_connection() -> None:
    result = _resolve_catchment_source_id(None, _SOURCE)
    assert uuid.UUID(result)
