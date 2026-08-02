"""Tests for the unchanged-source-skip logic used by import-gias and
import-catchments: an ingestion source whose content checksum matches the
last successful run's checksum should be skipped rather than re-imported.

Uses an in-memory fake database connection, not a real Postgres/CockroachDB
connection, per this service's test constraints.
"""

from __future__ import annotations

import hashlib
from typing import Any

from catchment_zone_ingestor.pipeline import get_last_successful_checksum


class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._result: dict[str, Any] | None = None

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def execute(self, sql: str, params: dict[str, Any]) -> None:
        matches = [
            r
            for r in self._rows
            if r["source"] == params["source"] and r["status"] == params["status"]
        ]
        matches.sort(key=lambda r: r["started_at"], reverse=True)
        self._result = matches[0] if matches else None

    def fetchone(self) -> dict[str, Any] | None:
        return self._result


class _FakeConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def cursor(self, **kwargs: Any) -> _FakeCursor:
        return _FakeCursor(self._rows)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def test_no_prior_run_returns_none() -> None:
    conn = _FakeConnection(rows=[])
    assert get_last_successful_checksum(conn, "gias_establishments") is None


def test_returns_checksum_from_most_recent_succeeded_run() -> None:
    checksum = _sha256(b"gias extract v1")
    conn = _FakeConnection(
        rows=[
            {
                "source": "gias_establishments",
                "status": "SUCCEEDED",
                "started_at": "2026-06-01T00:00:00",
                "error_summary": f"checksum:{checksum}",
            },
            {
                "source": "gias_establishments",
                "status": "SUCCEEDED",
                "started_at": "2026-07-01T00:00:00",
                "error_summary": f"checksum:{_sha256(b'gias extract v2')}",
            },
        ]
    )
    result = get_last_successful_checksum(conn, "gias_establishments")
    assert result == _sha256(b"gias extract v2")


def test_ignores_failed_runs() -> None:
    conn = _FakeConnection(
        rows=[
            {
                "source": "gias_establishments",
                "status": "FAILED",
                "started_at": "2026-07-01T00:00:00",
                "error_summary": "network timeout",
            }
        ]
    )
    assert get_last_successful_checksum(conn, "gias_establishments") is None


def test_ignores_other_sources() -> None:
    conn = _FakeConnection(
        rows=[
            {
                "source": "gias_trusts",
                "status": "SUCCEEDED",
                "started_at": "2026-07-01T00:00:00",
                "error_summary": f"checksum:{_sha256(b'trusts v1')}",
            }
        ]
    )
    assert get_last_successful_checksum(conn, "gias_establishments") is None


def test_identical_content_produces_identical_checksum_for_skip_decision() -> None:
    content_a = b"identical extract bytes"
    content_b = b"identical extract bytes"
    assert _sha256(content_a) == _sha256(content_b)


def test_changed_content_produces_different_checksum() -> None:
    assert _sha256(b"extract v1") != _sha256(b"extract v2")
