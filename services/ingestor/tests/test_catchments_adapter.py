"""Tests for the ArcGIS catchment feature adapter's geometry-building step,
using tests/fixtures/sheffield_catchment_sample.geojson: an invented fixture
(clearly marked as such in the file) with coordinates inside Sheffield's real
bounding box but no relationship to any actual published catchment boundary.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest
from shapely.geometry import Point

from catchment_zone_ingestor.adapters import catchments as catchments_adapter
from catchment_zone_ingestor.adapters.catchments import (
    CatchmentSourceError,
    build_catchment_areas,
    download_geojson_features,
    reproject_if_needed,
)

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


def test_reproject_if_needed_leaves_confirmed_wgs84_geometry_alone() -> None:
    point = Point(-1.47, 53.38)
    result = reproject_if_needed(point, detected_wkid=4326, fallback_source_crs="EPSG:27700")
    assert result.x == point.x
    assert result.y == point.y


def test_reproject_if_needed_leaves_geometry_alone_when_no_crs_reported_and_source_is_already_wgs84() -> (
    None
):
    point = Point(-1.47, 53.38)
    result = reproject_if_needed(point, detected_wkid=None, fallback_source_crs="EPSG:4326")
    assert result.x == point.x
    assert result.y == point.y


def test_reproject_if_needed_reprojects_when_no_crs_reported_but_source_is_declared_bng() -> None:
    """Regression test: shapefile_zip sources (Aberdeenshire, Orkney
    Islands) never get a crs block from the server (detected_wkid is
    always None, see download_shapefile_zip_features), so this must fall
    back to the source's own declared CRS rather than assuming WGS84 -
    verified live that skipping this silently left British National Grid
    easting/northing values (e.g. ~340000, ~1000000) sitting in what the
    rest of the app treats as WGS84 longitude/latitude columns."""
    # Approximately Sheffield city centre in EPSG:27700 (BNG).
    bng_point = Point(433800, 387200)
    result = reproject_if_needed(bng_point, detected_wkid=None, fallback_source_crs="EPSG:27700")
    assert -2.0 < result.x < -1.0
    assert 53.0 < result.y < 53.6


def test_reproject_if_needed_reprojects_when_server_explicitly_reports_non_wgs84_crs() -> None:
    bng_point = Point(433800, 387200)
    result = reproject_if_needed(bng_point, detected_wkid=27700, fallback_source_crs="EPSG:27700")
    assert -2.0 < result.x < -1.0
    assert 53.0 < result.y < 53.6


# Invented WFS 1.1.0 GML3 response, shaped like North Lincolnshire's real
# GetOWS.ashx output (verified live) but with small round-number
# coordinates rather than real British National Grid values - no
# relationship to any actual published catchment boundary.
_GML_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection
    xmlns:ms="http://mapserver.gis.umn.edu/mapserver"
    xmlns:gml="http://www.opengis.net/gml"
    xmlns:wfs="http://www.opengis.net/wfs">
  <gml:featureMember>
    <ms:Primary_Catchments gml:id="Primary_Catchments.1">
      <ms:school>Test Multi-Part Primary (fixture)</ms:school>
      <ms:sch_level>Primary</ms:sch_level>
      <ms:msGeometry>
        <gml:MultiSurface srsName="EPSG:27700">
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList srsDimension="2">0 0 10 0 10 10 0 10 0 0</gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
          <gml:surfaceMember>
            <gml:Polygon>
              <gml:exterior>
                <gml:LinearRing>
                  <gml:posList srsDimension="2">100 100 110 100 110 110 100 110 100 100</gml:posList>
                </gml:LinearRing>
              </gml:exterior>
            </gml:Polygon>
          </gml:surfaceMember>
        </gml:MultiSurface>
      </ms:msGeometry>
    </ms:Primary_Catchments>
  </gml:featureMember>
  <gml:featureMember>
    <ms:Primary_Catchments gml:id="Primary_Catchments.2">
      <ms:school>Test Primary With Hole (fixture)</ms:school>
      <ms:sch_level>Primary</ms:sch_level>
      <ms:msGeometry>
        <gml:Polygon srsName="EPSG:27700">
          <gml:exterior>
            <gml:LinearRing>
              <gml:posList srsDimension="2">0 0 20 0 20 20 0 20 0 0</gml:posList>
            </gml:LinearRing>
          </gml:exterior>
          <gml:interior>
            <gml:LinearRing>
              <gml:posList srsDimension="2">5 5 15 5 15 15 5 15 5 5</gml:posList>
            </gml:LinearRing>
          </gml:interior>
        </gml:Polygon>
      </ms:msGeometry>
    </ms:Primary_Catchments>
  </gml:featureMember>
</wfs:FeatureCollection>
"""


def _gml_feature_members() -> list[ET.Element]:
    root = ET.fromstring(_GML_FIXTURE)
    return root.findall("{http://www.opengis.net/gml}featureMember")


def test_gml_parser_turns_multisurface_into_multipolygon_with_both_parts() -> None:
    member = _gml_feature_members()[0]
    feature = catchments_adapter._gml_feature_member_to_geojson(member, "Primary_Catchments")
    assert feature["properties"]["school"] == "Test Multi-Part Primary (fixture)"
    assert feature["properties"]["sch_level"] == "Primary"
    assert feature["geometry"]["type"] == "MultiPolygon"
    assert len(feature["geometry"]["coordinates"]) == 2
    assert feature["geometry"]["coordinates"][0][0][0] == [0.0, 0.0]
    assert feature["geometry"]["coordinates"][1][0][0] == [100.0, 100.0]


def test_gml_parser_turns_polygon_with_interior_into_polygon_with_hole() -> None:
    member = _gml_feature_members()[1]
    feature = catchments_adapter._gml_feature_member_to_geojson(member, "Primary_Catchments")
    assert feature["properties"]["school"] == "Test Primary With Hole (fixture)"
    assert feature["geometry"]["type"] == "Polygon"
    # exterior ring + one interior ring (the hole)
    assert len(feature["geometry"]["coordinates"]) == 2
    assert feature["geometry"]["coordinates"][1][0] == [5.0, 5.0]


def test_gml_parsed_features_flow_through_build_catchment_areas_with_bng_reprojection() -> None:
    """End-to-end: GML-parsed features (still in native EPSG:27700, as
    query_all_wfs_gml_features always returns them) reprojected to
    plausible WGS84 by the same build_catchment_areas step every other
    source type goes through."""
    features = [
        catchments_adapter._gml_feature_member_to_geojson(member, "Primary_Catchments")
        for member in _gml_feature_members()
    ]
    # Use realistic BNG coordinates (roughly North Lincolnshire) instead of
    # the tiny 0..20 fixture range, so the reprojected result lands in a
    # sane WGS84 range to assert against.
    features[1]["geometry"] = {
        "type": "Polygon",
        "coordinates": [
            [
                [488000.0, 408000.0],
                [489000.0, 408000.0],
                [489000.0, 409000.0],
                [488000.0, 409000.0],
                [488000.0, 408000.0],
            ]
        ],
    }
    result = build_catchment_areas(
        [features[1]],
        source_id="894:primary_catchment",
        area_type="primary_catchment",
        academic_year="2025-2026",
        name_field_candidates=["school"],
        detected_wkid=None,
        fallback_source_crs="EPSG:27700",
        valid_from_iso="2025-09-01T00:00:00",
    )
    assert result.rejected_count == 0
    area = result.areas[0]
    assert area.area_name == "Test Primary With Hole (fixture)"
    assert -1.0 < area.minimum_longitude < 0.0
    assert 53.0 < area.minimum_latitude < 54.0


def test_download_geojson_features_returns_features_with_no_detected_wkid() -> None:
    """Nottinghamshire's bespoke schoolsearchapi returns a single, already-
    complete GeoJSON FeatureCollection with no crs block - unlike the
    ArcGIS/WFS adapters, there is no pagination and no query string."""
    body = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NAME": "Test Primary (fixture)"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-1.1, 53.0], [-1.0, 53.0], [-1.0, 53.1], [-1.1, 53.1], [-1.1, 53.0]]
                    ],
                },
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.query == b""
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = download_geojson_features(client, "https://example.invalid/api/catchments")

    assert result.detected_wkid is None
    assert len(result.features) == 1
    assert result.features[0]["properties"]["NAME"] == "Test Primary (fixture)"


def test_download_geojson_features_rejects_non_feature_collection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"type": "Point", "coordinates": [0, 0]})

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(CatchmentSourceError),
    ):
        download_geojson_features(client, "https://example.invalid/api/catchments")
