import {
  booleanPointInPolygon,
  distance as turfDistance,
  flatten,
  point as turfPoint,
  polygonToLine,
  pointToLineDistance,
} from "@turf/turf";
import type { Geometry, MultiPolygon, Polygon } from "geojson";

/** Cheap bounding-box containment check against the CatchmentArea table's
 * min/max lat/lon columns, used to prefilter candidate polygons before the
 * more expensive precise point-in-polygon test. */
export function isPointInBbox(
  lat: number,
  lon: number,
  bounds: {
    minimumLatitude: number;
    maximumLatitude: number;
    minimumLongitude: number;
    maximumLongitude: number;
  },
): boolean {
  return (
    lat >= bounds.minimumLatitude &&
    lat <= bounds.maximumLatitude &&
    lon >= bounds.minimumLongitude &&
    lon <= bounds.maximumLongitude
  );
}

/** Parses a CatchmentArea's stored GeoJSON geometry string. Returns null
 * (rather than throwing) for malformed data, so one bad geometry record
 * cannot 500 a catchment check for every other area. */
export function parseCatchmentGeometry(
  geometryGeojson: string,
): Polygon | MultiPolygon | null {
  try {
    const parsed = JSON.parse(geometryGeojson) as Geometry;
    if (parsed.type === "Polygon" || parsed.type === "MultiPolygon") {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

/** Precise point-in-polygon test via Turf, after the bbox prefilter has
 * already narrowed the candidate set. */
export function isPointInGeometry(
  lat: number,
  lon: number,
  geometry: Polygon | MultiPolygon,
): boolean {
  return booleanPointInPolygon(turfPoint([lon, lat]), geometry);
}

/** Straight-line distance in metres from a point to the nearest edge of a
 * polygon's boundary. Used to decide whether a postcode-centroid result is
 * close enough to a catchment edge to warrant the near-boundary warning. */
export function distanceToBoundaryMetres(
  lat: number,
  lon: number,
  geometry: Polygon | MultiPolygon,
): number {
  const boundary = polygonToLine(geometry);
  const pt = turfPoint([lon, lat]);
  // polygonToLine returns a LineString feature for a Polygon but a
  // MultiLineString feature (or feature collection) for a MultiPolygon;
  // flatten normalises every shape into single-LineString features so
  // pointToLineDistance, which only accepts LineString, always works.
  const lines = flatten(boundary);
  const distances = lines.features.map((f) =>
    pointToLineDistance(pt, f, { units: "meters" }),
  );
  return Math.min(...distances);
}

/** Great-circle distance in kilometres between two points, used for the
 * "distance from a point" school search sort/filter. */
export function distanceKm(
  a: { lat: number; lon: number },
  b: { lat: number; lon: number },
): number {
  return turfDistance(turfPoint([a.lon, a.lat]), turfPoint([b.lon, b.lat]), {
    units: "kilometers",
  });
}

/** Expands a centre point by a radius (km) into a bounding box, for a
 * cheap pre-filter before an exact distance calculation and sort. Uses an
 * equirectangular approximation, which is accurate enough at the radii
 * this search supports (<= 100km) for a prefilter, not the final sort. */
export function boundingBoxAroundPoint(
  lat: number,
  lon: number,
  radiusKm: number,
): { minLat: number; maxLat: number; minLon: number; maxLon: number } {
  const latDelta = radiusKm / 111; // ~111km per degree of latitude
  const lonDelta = radiusKm / (111 * Math.cos((lat * Math.PI) / 180) || 1);
  return {
    minLat: lat - latDelta,
    maxLat: lat + latDelta,
    minLon: lon - lonDelta,
    maxLon: lon + lonDelta,
  };
}
