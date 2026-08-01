"""Tests for the GIAS establishment CSV adapter.

tests/fixtures/gias_sample.csv is an entirely invented fixture: URNs
900001-900008 and every school name in it are fake and do not describe any
real school.
"""

from __future__ import annotations

from pathlib import Path

from schoolscope_ingestor.adapters.gias import parse_establishment_csv
from schoolscope_ingestor.models import SchoolStatus

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gias_sample.csv"


def _load_fixture_bytes() -> bytes:
    return FIXTURE_PATH.read_bytes()


def test_parses_all_valid_rows() -> None:
    result = parse_establishment_csv(_load_fixture_bytes())
    valid_urns = {s.urn for s in result.schools}
    assert valid_urns == {"900001", "900002", "900003", "900007", "900008"}


def test_rejects_blank_establishment_name() -> None:
    result = parse_establishment_csv(_load_fixture_bytes())
    assert "900004" not in {s.urn for s in result.schools}


def test_rejects_non_numeric_urn() -> None:
    result = parse_establishment_csv(_load_fixture_bytes())
    assert not any(s.urn.startswith("900005") for s in result.schools)


def test_rejects_unrecognised_status() -> None:
    result = parse_establishment_csv(_load_fixture_bytes())
    assert "900006" not in {s.urn for s in result.schools}


def test_row_counts_and_rejection_samples() -> None:
    result = parse_establishment_csv(_load_fixture_bytes())
    assert result.rows_processed == 8
    assert result.rows_rejected == 3
    assert len(result.schools) == 5
    assert len(result.rejection_samples) == 3


def test_header_mapping_maps_key_fields() -> None:
    result = parse_establishment_csv(_load_fixture_bytes())
    ashfield = next(s for s in result.schools if s.urn == "900001")
    assert ashfield.school_name == "Ashfield Community Primary School"
    assert ashfield.normalised_name == "ashfield community primary school"
    assert ashfield.status == SchoolStatus.OPEN
    assert ashfield.phase_name == "Primary"
    assert ashfield.minimum_age == 3
    assert ashfield.maximum_age == 11
    assert ashfield.postcode == "S10 1AB"
    assert ashfield.postcode_prefix == "S10"
    assert ashfield.local_authority_code == "373"


def test_closed_school_status_mapped() -> None:
    result = parse_establishment_csv(_load_fixture_bytes())
    closed = next(s for s in result.schools if s.urn == "900003")
    assert closed.status == SchoolStatus.CLOSED
    assert closed.closing_date is not None


def test_trust_linked_school_has_trust_id() -> None:
    result = parse_establishment_csv(_load_fixture_bytes())
    academy = next(s for s in result.schools if s.urn == "900002")
    assert academy.trust_id == "TR00123"


def test_row_limit_truncates_processing() -> None:
    result = parse_establishment_csv(_load_fixture_bytes(), row_limit=2)
    assert result.rows_processed == 2
    assert len(result.schools) == 2
