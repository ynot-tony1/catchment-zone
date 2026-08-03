"""Tests for the ArcGIS catchment feature adapter's geometry-building step,
using tests/fixtures/sheffield_catchment_sample.geojson: an invented fixture
(clearly marked as such in the file) with coordinates inside Sheffield's real
bounding box but no relationship to any actual published catchment boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

from catchment_zone_ingestor.adapters.catchments import build_catchment_areas

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sheffield_catchment_sample.geojson"


def _load_features() -> list[dict[str, object]]:
    data = json.loads(FIXTURE_PATH.read_text())
    return data["features"]  # type: ignore[no-any-return]


def test_builds_valid_polygon_and_polygon_with_hole() -> None:
    result = build_catchment_areas(
        _load_features(),
        source_id="373:primary_catchment",
        area_type="primary_catchment",
        academic_year="2025-2026",
        name_field_candidates=["NAME"],
        detected_wkid=4326,
        fallback_source_crs="EPSG:27700",
        valid_from_iso="2025-09-01T00:00:00",
    )
    names = {a.area_name for a in result.areas}
    assert "Test Primary Catchment A (fixture)" in names
    assert "Test Primary Catchment B, with hole (fixture)" in names


def test_rejects_non_polygonal_feature() -> None:
    result = build_catchment_areas(
        _load_features(),
        source_id="373:secondary_catchment",
        area_type="secondary_catchment",
        academic_year="2025-2026",
        name_field_candidates=["NAME"],
        detected_wkid=4326,
        fallback_source_crs="EPSG:27700",
        valid_from_iso="2025-09-01T00:00:00",
    )
    assert result.rejected_count == 1
    assert len(result.areas) == 2
    assert any("malformed non-polygon" in sample for sample in result.rejection_samples)


def test_bbox_and_checksum_populated() -> None:
    result = build_catchment_areas(
        _load_features(),
        source_id="373:primary_catchment",
        area_type="primary_catchment",
        academic_year="2025-2026",
        name_field_candidates=["NAME"],
        detected_wkid=4326,
        fallback_source_crs="EPSG:27700",
        valid_from_iso="2025-09-01T00:00:00",
    )
    area = result.areas[0]
    assert area.minimum_longitude < area.maximum_longitude
    assert area.minimum_latitude < area.maximum_latitude
    assert len(area.geometry_checksum) == 64  # sha256 hex digest length
    assert area.simplified_geometry_geojson is not None


def test_geometry_survives_as_geojson_polygon_with_interior_ring() -> None:
    result = build_catchment_areas(
        _load_features(),
        source_id="373:primary_catchment",
        area_type="primary_catchment",
        academic_year="2025-2026",
        name_field_candidates=["NAME"],
        detected_wkid=4326,
        fallback_source_crs="EPSG:27700",
        valid_from_iso="2025-09-01T00:00:00",
    )
    with_hole = next(a for a in result.areas if "hole" in a.area_name)
    geometry = json.loads(with_hole.geometry_geojson)
    assert geometry["type"] == "Polygon"
    assert len(geometry["coordinates"]) == 2  # exterior ring + one interior ring (the hole)


def test_strips_xyzm_coordinates_from_arcgis_features() -> None:
    """South Lanarkshire's Non-Denominational catchments layer returns 4D
    [lon, lat, z, m] coordinates with a null M (measure) value on every
    point, verified live - shapely.shape() cannot parse a 4-tuple with a
    None in it. build_catchment_areas must strip anything past X,Y rather
    than rejecting every feature from a source shaped like this.
    """
    feature = {
        "type": "Feature",
        "properties": {"ND_PS": "XYZM Test Primary School"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-1.5, 53.4, 0, None],
                    [-1.4, 53.4, 0, None],
                    [-1.4, 53.5, 0, None],
                    [-1.5, 53.5, 0, None],
                    [-1.5, 53.4, 0, None],
                ]
            ],
        },
    }
    result = build_catchment_areas(
        [feature],
        source_id="S12000029:primary_catchment_nd",
        area_type="primary_catchment_nd",
        academic_year="2025-2026",
        name_field_candidates=["ND_PS"],
        detected_wkid=4326,
        fallback_source_crs="EPSG:4326",
        valid_from_iso="2025-09-01T00:00:00",
    )
    assert result.rejected_count == 0
    assert len(result.areas) == 1
    assert result.areas[0].area_name == "XYZM Test Primary School"


def test_strips_trailing_whitespace_from_fixed_width_name_fields() -> None:
    """Bracknell Forest's source fields are fixed-width and pad every
    value with trailing spaces, verified live (e.g. "Harmans Water
    Primary School" followed by ~20 trailing spaces) - a source
    formatting artifact, not part of the real name."""
    feature = {
        "type": "Feature",
        "properties": {"Description": "Harmans Water Primary School                      "},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[-0.75, 51.4], [-0.74, 51.4], [-0.74, 51.41], [-0.75, 51.41], [-0.75, 51.4]]
            ],
        },
    }
    result = build_catchment_areas(
        [feature],
        source_id="867:primary_catchment",
        area_type="primary_catchment",
        academic_year="2025-2026",
        name_field_candidates=["Description"],
        detected_wkid=4326,
        fallback_source_crs="EPSG:4326",
        valid_from_iso="2025-09-01T00:00:00",
    )
    assert result.areas[0].area_name == "Harmans Water Primary School"
