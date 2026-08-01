"""Tests for shared geometry helpers: validation/repair, bbox, simplification,
checksum and point-in-polygon, covering plain polygons, polygons with holes,
and multipolygons."""

from __future__ import annotations

from shapely.geometry import LineString, MultiPolygon, Polygon

from schoolscope_ingestor.geometry import (
    InvalidGeometryError,
    compute_bbox,
    compute_geometry_checksum,
    point_in_polygon,
    simplify_geometry,
    validate_and_repair,
)

SQUARE = Polygon([(-1.48, 53.38), (-1.46, 53.38), (-1.46, 53.40), (-1.48, 53.40), (-1.48, 53.38)])

SQUARE_WITH_HOLE = Polygon(
    shell=[(-1.44, 53.41), (-1.40, 53.41), (-1.40, 53.44), (-1.44, 53.44), (-1.44, 53.41)],
    holes=[[(-1.435, 53.415), (-1.425, 53.415), (-1.425, 53.425), (-1.435, 53.425), (-1.435, 53.415)]],
)

# Classic bowtie: self-intersecting, invalid until repaired.
BOWTIE = Polygon([(-1.52, 53.36), (-1.50, 53.38), (-1.52, 53.38), (-1.50, 53.36), (-1.52, 53.36)])

MULTI = MultiPolygon(
    [
        Polygon([(-1.48, 53.38), (-1.46, 53.38), (-1.46, 53.40), (-1.48, 53.40)]),
        Polygon([(-1.44, 53.41), (-1.40, 53.41), (-1.40, 53.44), (-1.44, 53.44)]),
    ]
)


def test_valid_polygon_passes_through_unchanged() -> None:
    result = validate_and_repair(SQUARE)
    assert result.equals(SQUARE)
    assert result.is_valid


def test_polygon_with_hole_preserves_hole() -> None:
    result = validate_and_repair(SQUARE_WITH_HOLE)
    assert result.geom_type == "Polygon"
    assert len(list(result.interiors)) == 1


def test_multipolygon_supported() -> None:
    result = validate_and_repair(MULTI)
    assert result.geom_type == "MultiPolygon"
    assert result.is_valid


def test_bowtie_is_repaired_into_valid_geometry() -> None:
    assert not BOWTIE.is_valid
    result = validate_and_repair(BOWTIE)
    assert result.is_valid
    assert not result.is_empty
    assert result.geom_type in ("Polygon", "MultiPolygon")


def test_non_polygonal_geometry_is_rejected() -> None:
    line = LineString([(-1.52, 53.36), (-1.50, 53.38)])
    try:
        validate_and_repair(line)
        raised = False
    except InvalidGeometryError:
        raised = True
    assert raised


def test_bbox_matches_known_extent() -> None:
    min_lon, min_lat, max_lon, max_lat = compute_bbox(SQUARE)
    assert min_lon == -1.48
    assert max_lon == -1.46
    assert min_lat == 53.38
    assert max_lat == 53.40


def test_bbox_for_multipolygon_covers_all_parts() -> None:
    min_lon, min_lat, max_lon, max_lat = compute_bbox(MULTI)
    assert min_lon == -1.48
    assert max_lon == -1.40
    assert min_lat == 53.38
    assert max_lat == 53.44


def test_point_in_polygon_inside() -> None:
    assert point_in_polygon(-1.47, 53.39, SQUARE) is True


def test_point_in_polygon_outside() -> None:
    assert point_in_polygon(-1.30, 53.39, SQUARE) is False


def test_point_in_polygon_inside_hole_is_outside() -> None:
    assert point_in_polygon(-1.43, 53.42, SQUARE_WITH_HOLE) is False


def test_point_on_boundary_counts_as_inside() -> None:
    # covers() treats the boundary as inside, unlike contains().
    assert point_in_polygon(-1.48, 53.39, SQUARE) is True


def test_point_near_boundary_but_outside() -> None:
    assert point_in_polygon(-1.4801, 53.39, SQUARE) is False


def test_simplify_round_trip_preserves_validity_and_rough_shape() -> None:
    simplified = simplify_geometry(SQUARE, tolerance=0.001)
    assert simplified.is_valid
    assert not simplified.is_empty
    # A coarse simplification of a simple square should stay close in area.
    assert abs(simplified.area - SQUARE.area) / SQUARE.area < 0.05


def test_simplify_falls_back_to_original_if_result_empty() -> None:
    tiny = Polygon([(0, 0), (0.0000001, 0), (0.0000001, 0.0000001), (0, 0.0000001)])
    simplified = simplify_geometry(tiny, tolerance=1.0)
    assert not simplified.is_empty


def test_checksum_is_stable_for_identical_geometry() -> None:
    a = compute_geometry_checksum(SQUARE)
    b = compute_geometry_checksum(Polygon([(-1.48, 53.38), (-1.46, 53.38), (-1.46, 53.40), (-1.48, 53.40), (-1.48, 53.38)]))
    assert a == b


def test_checksum_differs_for_different_geometry() -> None:
    a = compute_geometry_checksum(SQUARE)
    b = compute_geometry_checksum(MULTI)
    assert a != b
