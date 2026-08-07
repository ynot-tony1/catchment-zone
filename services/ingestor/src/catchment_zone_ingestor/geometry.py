"""Shared geometry helpers.

These operate on shapely geometries in WGS84 (EPSG:4326, the CRS the database
stores geometry in) and mirror, in spirit, what apps/web will later do
server-side in TypeScript for point-in-polygon membership checks. Keeping the
logic here small and dependency-light (shapely only) makes it easy to port.

None of these helpers ever claim that a point falling inside a catchment
polygon guarantees a school place; see adapters/catchments.py and
adapters/admissions.py for the caveats this service is required to preserve.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid

#: Default simplification tolerance in degrees for the display geometry.
#: Roughly 10 metres at England's latitudes. Coarser than the stored,
#: full-precision geometry; used only for map rendering, never for the
#: authoritative point-in-polygon check.
DEFAULT_SIMPLIFY_TOLERANCE_DEGREES = 0.0001

#: Simplification tolerance in degrees for the /map page's whole-of-Great-
#: Britain overview layer, which loads every catchment area at once.
#: Roughly 100 metres at England's latitudes - imperceptible at the zoom
#: level where a whole-country view is even legible, but a large reduction
#: in point count (and therefore transfer size) versus
#: DEFAULT_SIMPLIFY_TOLERANCE_DEGREES. Never used for anything other than
#: this one bulk display case.
OVERVIEW_SIMPLIFY_TOLERANCE_DEGREES = 0.001


class InvalidGeometryError(ValueError):
    """Raised when a geometry cannot be repaired into a valid Polygon or MultiPolygon."""


def validate_and_repair(geometry: BaseGeometry) -> BaseGeometry:
    """Return a valid geometry, attempting repair if the input is invalid.

    Tries shapely's make_valid first (topology-preserving where possible),
    and falls back to the classic buffer(0) trick if make_valid still leaves
    an invalid or empty result. Raises InvalidGeometryError if neither repair
    produces a usable Polygon or MultiPolygon, so callers can reject and log
    the single offending feature rather than crashing the whole import.
    """
    if geometry.is_empty:
        raise InvalidGeometryError("geometry is empty")

    candidate = geometry
    if not candidate.is_valid:
        candidate = make_valid(candidate)

    if not candidate.is_valid or candidate.is_empty:
        candidate = geometry.buffer(0)

    if candidate.is_empty or not candidate.is_valid:
        raise InvalidGeometryError("geometry could not be repaired into a valid shape")

    if candidate.geom_type not in ("Polygon", "MultiPolygon"):
        # make_valid on a near-degenerate polygon can return a GeometryCollection
        # mixing points/lines with polygons. Only the polygonal parts are usable
        # for a catchment area.
        polygonal = [
            g
            for g in getattr(candidate, "geoms", [candidate])
            if g.geom_type in ("Polygon", "MultiPolygon")
        ]
        if not polygonal:
            raise InvalidGeometryError(
                f"repaired geometry has no polygonal component (got {candidate.geom_type})"
            )
        from shapely.ops import unary_union

        candidate = unary_union(polygonal)

    return candidate


def geojson_to_geometry(geojson_geometry: dict[str, Any]) -> BaseGeometry:
    """Parse a GeoJSON geometry dict into a shapely geometry."""
    return shape(geojson_geometry)


def geometry_to_geojson_str(geometry: BaseGeometry) -> str:
    """Serialise a shapely geometry to a compact GeoJSON string (no whitespace)."""
    return json.dumps(geometry.__geo_interface__, separators=(",", ":"))


def compute_bbox(geometry: BaseGeometry) -> tuple[float, float, float, float]:
    """Return (min_longitude, min_latitude, max_longitude, max_latitude)."""
    min_lon, min_lat, max_lon, max_lat = geometry.bounds
    return (min_lon, min_lat, max_lon, max_lat)


def simplify_geometry(
    geometry: BaseGeometry, tolerance: float = DEFAULT_SIMPLIFY_TOLERANCE_DEGREES
) -> BaseGeometry:
    """Return a simplified copy of geometry for display purposes.

    Uses Douglas-Peucker simplification via shapely with topology preservation
    enabled, so simplified polygons never self-intersect even though vertex
    count is reduced. This simplified geometry is for map rendering only; the
    full-precision geometry remains the source of truth for point-in-polygon
    membership checks.
    """
    simplified = geometry.simplify(tolerance, preserve_topology=True)
    if simplified.is_empty:
        # Simplification tolerance was too aggressive for a small polygon.
        # Fall back to the original geometry rather than losing the area entirely.
        return geometry
    return simplified


def compute_geometry_checksum(geometry: BaseGeometry) -> str:
    """SHA-256 checksum of a geometry's canonical GeoJSON representation.

    Used to detect whether a catchment polygon has actually changed between
    ingestion runs (coordinates differ), independent of the source file's own
    checksum, which may change due to metadata-only edits.
    """
    canonical = geometry_to_geojson_str(geometry)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def point_in_polygon(longitude: float, latitude: float, geometry: BaseGeometry) -> bool:
    """Return True if the point (longitude, latitude) falls within geometry.

    Uses shapely's `covers` rather than `contains` so that a point exactly on
    the boundary counts as inside, matching how most catchment map UIs treat
    an edge case. This is a geometric containment check only; it says nothing
    about whether a school would offer a place, and callers must not present
    it as such.
    """
    from shapely.geometry import Point

    return bool(geometry.covers(Point(longitude, latitude)))
