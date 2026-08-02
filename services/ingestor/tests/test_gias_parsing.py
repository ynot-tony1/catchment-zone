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


def test_derives_no_local_authorities_without_an_la_name_column() -> None:
    """The shared fixture has LA (code) but no LA (name) column (it predates
    local authority derivation); this must not crash or invent a name."""
    result = parse_establishment_csv(_load_fixture_bytes())
    assert result.local_authorities == []


def test_derives_distinct_local_authorities_from_la_code_and_name() -> None:
    csv_bytes = (
        b"URN,EstablishmentName,TypeOfEstablishment (name),EstablishmentStatus (name),"
        b"PhaseOfEducation (name),LA (code),LA (name)\r\n"
        b"900001,Test School One,Community school,Open,Primary,373,Sheffield\r\n"
        b"900002,Test School Two,Community school,Open,Primary,373,Sheffield\r\n"
        b"900003,Test School Three,Community school,Open,Primary,201,Barnsley\r\n"
    )
    result = parse_establishment_csv(csv_bytes)
    assert {(la.code, la.name) for la in result.local_authorities} == {
        ("373", "Sheffield"),
        ("201", "Barnsley"),
    }


def test_local_authority_derivation_never_rejects_a_row() -> None:
    """A blank LA (name) for one row must not affect that row's school or
    any other row's derived local authority."""
    csv_bytes = (
        b"URN,EstablishmentName,TypeOfEstablishment (name),EstablishmentStatus (name),"
        b"PhaseOfEducation (name),LA (code),LA (name)\r\n"
        b"900001,Test School,Community school,Open,Primary,373,\r\n"
    )
    result = parse_establishment_csv(csv_bytes)
    assert result.rows_rejected == 0
    assert len(result.schools) == 1
    assert result.local_authorities == []


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
