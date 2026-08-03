"""Tests for the DfE Explore Education Statistics (EES) performance-tables
adapter functions: format_academic_year, cell classification, and mapping
raw school-performance-tables CSV rows to SchoolMetric records.

The row fixtures below are entirely invented (URNs and school-adjacent
values are made up) but shaped exactly like the real key-stage-4-performance
"Performance tables schools data" CSV, verified live against the DfE
Explore Education Statistics API on 2026-08-02.
"""

from __future__ import annotations

from catchment_zone_ingestor.adapters.statistics import (
    ResolvedRelease,
    format_academic_year,
    map_performance_rows_to_metrics,
)

_RELEASE = ResolvedRelease(
    publication_slug="key-stage-4-performance",
    dataset_id="test-dataset-id",
    release_id="1.0.2",
    release_label="1.0.2",
    is_provisional=False,
    published_at="2026-04-23T08:30:49+00:00",
)

_KS4_DATASET_CONFIG = {
    "urn_field": "school_urn",
    "time_period_field": "time_period",
    "headline_filter": {"breakdown_topic": "Total", "breakdown": "Total"},
    "metrics": [
        {"metric_code": "attainment8_average", "column": "attainment8_average"},
        {"metric_code": "progress8_average", "column": "progress8_average"},
    ],
}


def test_format_academic_year_converts_compact_time_period() -> None:
    assert format_academic_year("202425") == "2024-2025"


def test_format_academic_year_leaves_unrecognised_shape_unchanged() -> None:
    assert format_academic_year("2024-2025") == "2024-2025"
    assert format_academic_year("") == ""


def test_maps_headline_row_to_metrics() -> None:
    rows = [
        {
            "school_urn": "999001",
            "time_period": "202425",
            "breakdown_topic": "Total",
            "breakdown": "Total",
            "attainment8_average": "45.6",
            "progress8_average": "0.12",
        }
    ]
    metrics = list(map_performance_rows_to_metrics(rows, _KS4_DATASET_CONFIG, _RELEASE))
    assert len(metrics) == 2
    a8 = next(m for m in metrics if m.metric_code == "attainment8_average")
    p8 = next(m for m in metrics if m.metric_code == "progress8_average")
    assert a8.school_urn == "999001"
    assert a8.academic_year == "2024-2025"
    assert a8.value_numeric == 45.6
    assert a8.suppressed is False
    assert p8.value_numeric == 0.12


def test_ignores_subgroup_breakdown_rows() -> None:
    """Only breakdown_topic=Total/breakdown=Total rows (the whole-school
    figure) are imported; subgroup rows for the same school must not
    produce a second, conflicting metric row."""
    rows = [
        {
            "school_urn": "999001",
            "time_period": "202425",
            "breakdown_topic": "Total",
            "breakdown": "Total",
            "attainment8_average": "45.6",
            "progress8_average": "0.12",
        },
        {
            "school_urn": "999001",
            "time_period": "202425",
            "breakdown_topic": "Sex",
            "breakdown": "Boys",
            "attainment8_average": "42.1",
            "progress8_average": "0.05",
        },
    ]
    metrics = list(map_performance_rows_to_metrics(rows, _KS4_DATASET_CONFIG, _RELEASE))
    assert len(metrics) == 2
    assert all(m.value_numeric != 42.1 for m in metrics)


def test_not_applicable_marker_z_is_unavailable_not_suppressed() -> None:
    """DfE's "z" marker (verified live: e.g. progress8_average school-wide
    in the current release) means "not applicable", distinct from a
    small-cohort privacy suppression - must not be flagged suppressed."""
    rows = [
        {
            "school_urn": "999001",
            "time_period": "202425",
            "breakdown_topic": "Total",
            "breakdown": "Total",
            "attainment8_average": "45.6",
            "progress8_average": "z",
        }
    ]
    metrics = list(map_performance_rows_to_metrics(rows, _KS4_DATASET_CONFIG, _RELEASE))
    p8 = next(m for m in metrics if m.metric_code == "progress8_average")
    assert p8.value_numeric is None
    assert p8.suppressed is False


def test_suppressed_marker_c_is_flagged_suppressed() -> None:
    rows = [
        {
            "school_urn": "999001",
            "time_period": "202425",
            "breakdown_topic": "Total",
            "breakdown": "Total",
            "attainment8_average": "c",
            "progress8_average": "z",
        }
    ]
    metrics = list(map_performance_rows_to_metrics(rows, _KS4_DATASET_CONFIG, _RELEASE))
    a8 = next(m for m in metrics if m.metric_code == "attainment8_average")
    assert a8.value_numeric is None
    assert a8.suppressed is True


def test_skips_rows_missing_urn_or_time_period() -> None:
    rows = [
        {
            "school_urn": "",
            "time_period": "202425",
            "breakdown_topic": "Total",
            "breakdown": "Total",
            "attainment8_average": "45.6",
            "progress8_average": "0.1",
        },
        {
            "school_urn": "999002",
            "time_period": "",
            "breakdown_topic": "Total",
            "breakdown": "Total",
            "attainment8_average": "45.6",
            "progress8_average": "0.1",
        },
    ]
    metrics = list(map_performance_rows_to_metrics(rows, _KS4_DATASET_CONFIG, _RELEASE))
    assert metrics == []
