"""Tests for the Northern Ireland school register adapter.

tests/fixtures/northern_ireland_sample.csv is an entirely invented fixture:
Reference values, school names and addresses in it are fake and do not
describe any real Northern Ireland school. Its column shape matches the
real Open Data NI "School Locations" CSV, downloaded and inspected live
2026-08-02.
"""

from __future__ import annotations

from pathlib import Path

from catchment_zone_ingestor.adapters.northern_ireland import (
    NORTHERN_IRELAND_SOURCE_EXTRACT_DATE,
    parse_school_locations_csv,
)
from catchment_zone_ingestor.models import Nation, SchoolStatus

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "northern_ireland_sample.csv"


def _load_fixture_bytes() -> bytes:
    return FIXTURE_PATH.read_bytes()


def test_parses_valid_rows_and_rejects_blank_reference() -> None:
    result = parse_school_locations_csv(_load_fixture_bytes())
    valid_urns = {s.urn for s in result.schools}
    assert valid_urns == {"9900001", "9900002"}
    assert result.rows_processed == 3
    assert result.rows_rejected == 1
    assert len(result.rejection_samples) == 1


def test_every_school_is_northern_ireland_nation_and_open() -> None:
    result = parse_school_locations_csv(_load_fixture_bytes())
    assert all(s.nation == Nation.NORTHERN_IRELAND for s in result.schools)
    assert all(s.status == SchoolStatus.OPEN for s in result.schools)


def test_every_school_carries_the_known_stale_extract_date() -> None:
    """The source is dated Feb 2016; every row must say so explicitly
    rather than being presented as if it were current."""
    result = parse_school_locations_csv(_load_fixture_bytes())
    assert all(s.source_extract_date == NORTHERN_IRELAND_SOURCE_EXTRACT_DATE for s in result.schools)


def test_field_mapping() -> None:
    result = parse_school_locations_csv(_load_fixture_bytes())
    primary = next(s for s in result.schools if s.urn == "9900001")
    assert primary.school_name == "Test Primary School (fixture)"
    assert primary.normalised_name == "test primary school (fixture)"
    assert primary.phase_name == "Primary school"
    assert primary.establishment_type_name == "Controlled"
    assert primary.county == "ANTRIM"
    assert primary.postcode == "BT1 1ST"
    assert primary.postcode_prefix == "BT1"
    assert primary.number_of_pupils == 210
    assert primary.latitude == 54.61253
    assert primary.longitude == -5.93645
    # No local-authority concept exists for Northern Ireland in this source.
    assert primary.local_authority_code is None


def test_row_limit_truncates_processing() -> None:
    result = parse_school_locations_csv(_load_fixture_bytes(), row_limit=2)
    assert result.rows_processed == 2
    assert len(result.schools) == 2
