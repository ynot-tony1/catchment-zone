"""Tests for the Wales school register adapter.

tests/fixtures/wales_sample.json is an entirely invented fixture: school_code
values, school names and addresses in it are fake and do not describe any
real Welsh school. Its shape matches a real response verified live against
https://datamap.gov.wales/geoserver/wfs (typeName geonode:maintained_schools_wg).
"""

from __future__ import annotations

import json
from pathlib import Path

from catchment_zone_ingestor.adapters.wales import parse_wales_schools
from catchment_zone_ingestor.models import Nation, SchoolStatus

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "wales_sample.json"


def _load_features() -> list[dict[str, object]]:
    data = json.loads(FIXTURE_PATH.read_text())
    return list(data["features"])


def test_parses_valid_features_and_rejects_invalid_school_code() -> None:
    result = parse_wales_schools(_load_features())
    valid_urns = {s.urn for s in result.schools}
    assert valid_urns == {"9900001", "6801234"}
    assert result.rows_processed == 3
    assert result.rows_rejected == 1
    assert len(result.rejection_samples) == 1


def test_every_school_is_wales_nation_and_open() -> None:
    result = parse_wales_schools(_load_features())
    assert all(s.nation == Nation.WALES for s in result.schools)
    assert all(s.status == SchoolStatus.OPEN for s in result.schools)


def test_field_mapping() -> None:
    result = parse_wales_schools(_load_features())
    primary = next(s for s in result.schools if s.urn == "9900001")
    assert primary.school_name == "Ysgol Prawf (fixture)"
    assert primary.normalised_name == "ysgol prawf (fixture)"
    assert primary.phase_name == "Nursery, Infants & Juniors"
    assert primary.establishment_type_name == "Community"
    # "---" must not be stored as a literal religious character.
    assert primary.religious_character is None
    assert primary.postcode == "LL1 1ST"
    assert primary.postcode_prefix == "LL1"
    assert primary.local_authority_code == "W-660"
    assert primary.number_of_pupils == 180
    assert primary.latitude == 53.41
    assert primary.longitude == -4.35
    assert primary.telephone == "01234567890"

    secondary = next(s for s in result.schools if s.urn == "6801234")
    assert secondary.religious_character == "Roman Catholic"
    assert secondary.county == "Fixture County"


def test_local_authority_codes_are_prefixed_to_avoid_england_collision() -> None:
    result = parse_wales_schools(_load_features())
    assert {(la.code, la.name) for la in result.local_authorities} == {
        ("W-660", "Test Anglesey"),
        ("W-680", "Test Cardiff"),
    }
    assert all(la.nation == Nation.WALES for la in result.local_authorities)


def test_row_limit_truncates_processing() -> None:
    result = parse_wales_schools(_load_features(), row_limit=2)
    assert result.rows_processed == 2
    assert len(result.schools) == 2
