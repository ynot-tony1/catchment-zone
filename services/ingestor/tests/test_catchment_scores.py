"""Tests for the catchment-area performance-percentile computation.

compute_percentiles and compute_catchment_scores are both pure functions
(no database, no I/O), so these tests cover the actual scoring logic
directly, including the geometry containment test - fixture coordinates
below are invented but shaped like a real small square catchment polygon
and points clearly inside/outside/on it.
"""

from __future__ import annotations

import pytest

from catchment_zone_ingestor.adapters.catchment_scores import (
    CatchmentAreaRow,
    SchoolPoint,
    compute_catchment_scores,
    compute_percentiles,
)

# A simple 1x1 degree square, roughly (-1, 51) to (0, 52).
_SQUARE_GEOJSON = (
    '{"type": "Polygon", "coordinates": '
    "[[[-1, 51], [0, 51], [0, 52], [-1, 52], [-1, 51]]]}"
)


def _area(area_type: str, nation: str) -> CatchmentAreaRow:
    return CatchmentAreaRow(
        id=f"area-{area_type}-{nation}",
        area_type=area_type,
        nation=nation,
        geometry_geojson=_SQUARE_GEOJSON,
        minimum_latitude=51,
        maximum_latitude=52,
        minimum_longitude=-1,
        maximum_longitude=0,
    )


def test_compute_percentiles_orders_low_to_high() -> None:
    values = {"a": 10.0, "b": 20.0, "c": 30.0}
    percentiles = compute_percentiles(values)
    assert percentiles["a"] < percentiles["b"] < percentiles["c"]
    # Mid-rank percentile for the top value of 3 is (2 less-than + 0.5
    # equal-to) / 3, not exactly 1.0 - that would overstate how it
    # compares to a hypothetical value just above it.
    assert percentiles["c"] == pytest.approx(2.5 / 3)


def test_compute_percentiles_ties_share_the_same_value() -> None:
    values = {"a": 10.0, "b": 10.0, "c": 20.0}
    percentiles = compute_percentiles(values)
    assert percentiles["a"] == percentiles["b"]
    assert percentiles["a"] < percentiles["c"]


def test_compute_percentiles_empty_input_returns_empty() -> None:
    assert compute_percentiles({}) == {}


def test_school_inside_polygon_gets_scored() -> None:
    area = _area("primary_catchment", "ENGLAND")
    schools = [SchoolPoint(urn="1", latitude=51.5, longitude=-0.5)]
    percentiles = {"ks2_rwm_expected_standard_percent": {"1": 0.75}}

    [result] = compute_catchment_scores([area], schools, percentiles)

    assert result.id == area.id
    assert result.performance_percentile == pytest.approx(0.75)
    assert result.performance_metric_code == "ks2_rwm_expected_standard_percent"


def test_school_outside_polygon_is_not_scored() -> None:
    area = _area("primary_catchment", "ENGLAND")
    schools = [SchoolPoint(urn="1", latitude=60.0, longitude=-0.5)]
    percentiles = {"ks2_rwm_expected_standard_percent": {"1": 0.75}}

    [result] = compute_catchment_scores([area], schools, percentiles)

    assert result.performance_percentile is None
    assert result.performance_metric_code is None


def test_multiple_schools_inside_polygon_are_averaged() -> None:
    area = _area("secondary_catchment", "ENGLAND")
    schools = [
        SchoolPoint(urn="1", latitude=51.2, longitude=-0.8),
        SchoolPoint(urn="2", latitude=51.8, longitude=-0.2),
    ]
    percentiles = {"attainment8_average": {"1": 0.2, "2": 0.8}}

    [result] = compute_catchment_scores([area], schools, percentiles)

    assert result.performance_percentile == pytest.approx(0.5)


def test_all_through_area_type_is_never_scored() -> None:
    """Orkney's all_through_catchment mixes primary-only and combined
    primary/secondary schools per feature - neither a primary nor a
    secondary metric would honestly describe every school it might
    contain, so it must always come back unscored."""
    area = _area("all_through_catchment", "ENGLAND")
    schools = [SchoolPoint(urn="1", latitude=51.5, longitude=-0.5)]
    percentiles = {
        "ks2_rwm_expected_standard_percent": {"1": 0.9},
        "attainment8_average": {"1": 0.9},
    }

    [result] = compute_catchment_scores([area], schools, percentiles)

    assert result.performance_percentile is None


def test_scotland_has_no_configured_metric_and_is_never_scored() -> None:
    area = _area("primary_catchment_nd", "SCOTLAND")
    schools = [SchoolPoint(urn="1", latitude=51.5, longitude=-0.5)]
    # Even if a percentile happened to exist under some metric code,
    # Scotland has no entry in the nation/phase candidate table at all.
    percentiles = {"ks2_rwm_expected_standard_percent": {"1": 0.9}}

    [result] = compute_catchment_scores([area], schools, percentiles)

    assert result.performance_percentile is None
    assert result.performance_metric_code is None


def test_school_with_no_percentile_for_the_metric_is_not_scored() -> None:
    """A school inside the polygon that simply has no value for the
    relevant metric (e.g. never published one) must not silently produce
    a score from zero schools' worth of data."""
    area = _area("secondary_catchment", "WALES")
    schools = [SchoolPoint(urn="1", latitude=51.5, longitude=-0.5)]
    percentiles = {"wales_ks4_capped9_points_score": {}}

    [result] = compute_catchment_scores([area], schools, percentiles)

    assert result.performance_percentile is None
