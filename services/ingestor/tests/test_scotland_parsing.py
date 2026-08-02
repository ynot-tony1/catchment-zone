"""Tests for the Scotland school register adapter.

tests/fixtures/scotland_sample.json is an entirely invented fixture: schuid
values, school names and addresses in it are fake and do not describe any
real Scottish school. Its shape matches a real response verified live
against https://maps.gov.scot/server/rest/services/ScotGov/UtilityGovernmental/MapServer/0/query.
"""

from __future__ import annotations

import json
from pathlib import Path

from catchment_zone_ingestor.adapters.scotland import parse_scotland_schools
from catchment_zone_ingestor.models import Nation, SchoolStatus

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "scotland_sample.json"


def _load_features() -> list[dict[str, object]]:
    data = json.loads(FIXTURE_PATH.read_text())
    return list(data["features"])


def test_parses_valid_features_and_rejects_blank_schuid() -> None:
    result = parse_scotland_schools(_load_features())
    valid_urns = {s.urn for s in result.schools}
    assert valid_urns == {"9900001P", "9900001S", "9900002SP"}
    assert result.rows_processed == 4
    assert result.rows_rejected == 1
    assert len(result.rejection_samples) == 1


def test_every_school_is_scotland_nation_and_open() -> None:
    result = parse_scotland_schools(_load_features())
    assert all(s.nation == Nation.SCOTLAND for s in result.schools)
    assert all(s.status == SchoolStatus.OPEN for s in result.schools)


def test_field_mapping() -> None:
    result = parse_scotland_schools(_load_features())
    primary = next(s for s in result.schools if s.urn == "9900001P")
    assert primary.school_name == "Test Primary School (fixture)"
    assert primary.normalised_name == "test primary school (fixture)"
    assert primary.phase_name == "Primary"
    assert primary.establishment_type_name == "Local Authority"
    assert primary.religious_character == "Non-denominational"
    assert primary.postcode == "TE1 1ST"
    assert primary.postcode_prefix == "TE1"
    assert primary.local_authority_code == "S99000001"
    assert primary.number_of_pupils == 210
    assert primary.latitude == 55.65
    assert primary.longitude == -4.7
    assert primary.telephone == "01234 567890"


def test_derives_distinct_local_authorities() -> None:
    result = parse_scotland_schools(_load_features())
    assert {(la.code, la.name) for la in result.local_authorities} == {
        ("S99000001", "Test Council"),
        ("S99000002", "Other Test Council"),
    }
    assert all(la.nation == Nation.SCOTLAND for la in result.local_authorities)


def test_row_limit_truncates_processing() -> None:
    result = parse_scotland_schools(_load_features(), row_limit=2)
    assert result.rows_processed == 2
    assert len(result.schools) == 2
