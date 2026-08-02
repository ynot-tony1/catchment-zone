"""Tests for suppressed vs provisional vs missing vs zero handling when
mapping DfE statistics rows to SchoolMetric records. Getting this wrong is a
data-integrity risk: a suppressed value must never be shown as zero, and a
zero must never be dropped as if it were missing."""

from __future__ import annotations

from catchment_zone_ingestor.adapters.statistics import (
    ResolvedRelease,
    _classify_cell,
    map_rows_to_metrics,
)


def _release(provisional: bool = False) -> ResolvedRelease:
    return ResolvedRelease(
        publication_slug="pupil-absence-in-schools-in-england",
        dataset_id="ds-1",
        release_id="rel-1",
        release_label="Academic year 2024/25",
        is_provisional=provisional,
        published_at="2026-03-01T00:00:00",
    )


def test_classify_genuine_zero_is_not_missing_or_suppressed() -> None:
    value, suppressed = _classify_cell("0")
    assert value == 0.0
    assert suppressed is False


def test_classify_suppressed_marker() -> None:
    for marker in ["c", "C", "x", "low", "SUPPRESSED", ":"]:
        value, suppressed = _classify_cell(marker)
        assert value is None
        assert suppressed is True, f"expected {marker!r} to be treated as suppressed"


def test_classify_not_applicable_marker_is_not_suppressed() -> None:
    value, suppressed = _classify_cell("n/a")
    assert value is None
    assert suppressed is False


def test_classify_blank_is_missing_not_suppressed() -> None:
    value, suppressed = _classify_cell("")
    assert value is None
    assert suppressed is False

    value, suppressed = _classify_cell(None)
    assert value is None
    assert suppressed is False


def test_classify_ordinary_numeric_value() -> None:
    value, suppressed = _classify_cell("94.3")
    assert value == 94.3
    assert suppressed is False


def test_classify_unrecognised_marker_defaults_to_suppressed() -> None:
    value, suppressed = _classify_cell("###")
    assert value is None
    assert suppressed is True


def test_map_rows_carries_suppression_through() -> None:
    rows = [
        {"school_urn": "900001", "time_period": "2024-2025", "overall_absence_rate": "c"},
        {"school_urn": "900002", "time_period": "2024-2025", "overall_absence_rate": "6.4"},
        {"school_urn": "900003", "time_period": "2024-2025", "overall_absence_rate": "0"},
    ]
    metrics = list(
        map_rows_to_metrics(
            iter(rows),
            metric_codes=["overall_absence_rate"],
            academic_year_field="time_period",
            school_urn_field="school_urn",
            release=_release(),
        )
    )
    by_urn = {m.school_urn: m for m in metrics}

    assert by_urn["900001"].suppressed is True
    assert by_urn["900001"].value_numeric is None

    assert by_urn["900002"].suppressed is False
    assert by_urn["900002"].value_numeric == 6.4

    # A genuine zero must survive as 0.0, not be treated as missing.
    assert by_urn["900003"].suppressed is False
    assert by_urn["900003"].value_numeric == 0.0


def test_map_rows_sets_provisional_flag_from_release() -> None:
    rows = [{"school_urn": "900001", "time_period": "2024-2025", "overall_absence_rate": "5.0"}]
    metrics = list(
        map_rows_to_metrics(
            iter(rows),
            metric_codes=["overall_absence_rate"],
            academic_year_field="time_period",
            school_urn_field="school_urn",
            release=_release(provisional=True),
        )
    )
    assert metrics[0].provisional is True


def test_map_rows_skips_rows_missing_urn_or_year() -> None:
    rows = [
        {"school_urn": "", "time_period": "2024-2025", "overall_absence_rate": "5.0"},
        {"school_urn": "900001", "time_period": "", "overall_absence_rate": "5.0"},
    ]
    metrics = list(
        map_rows_to_metrics(
            iter(rows),
            metric_codes=["overall_absence_rate"],
            academic_year_field="time_period",
            school_urn_field="school_urn",
            release=_release(),
        )
    )
    assert metrics == []


def test_map_rows_skips_missing_metric_columns() -> None:
    rows = [{"school_urn": "900001", "time_period": "2024-2025"}]
    metrics = list(
        map_rows_to_metrics(
            iter(rows),
            metric_codes=["overall_absence_rate"],
            academic_year_field="time_period",
            school_urn_field="school_urn",
            release=_release(),
        )
    )
    assert metrics == []
