import { NextRequest } from "next/server";
import { Prisma } from "@catchment-zone/database";
import { parseMapCatchmentsQuery } from "@catchment-zone/shared";
import { z } from "zod";
import {
  errorResponse,
  internalErrorResponse,
  jsonResponse,
  newRequestId,
} from "@/lib/api-response";
import { getPrismaClient } from "@/lib/prisma";
import { logger } from "@/lib/logger";

export const runtime = "nodejs";

type MapCatchmentRow = {
  id: string;
  area_name: string;
  area_type: string;
  academic_year: string;
  simplified_geometry_geojson: string;
  performance_percentile: number | null;
  performance_metric_code: string | null;
};

// Stored geometry carries ~8 decimal places (sub-millimetre) of precision,
// far beyond what a map display can render or a user can perceive - and
// since catchment areas are now loaded in full on every /map visit (see
// school-map.tsx), that precision was inflating a genuinely large payload
// for no visual benefit. 5 decimal places is ~1.1m at GB latitudes, well
// under this data's own real-world accuracy (digitised from paper maps in
// many cases). Cuts the full-dataset response by roughly half even before
// gzip compression.
const COORDINATE_DECIMAL_PLACES = 5;

function roundCoordinates(node: unknown): unknown {
  if (Array.isArray(node)) {
    if (
      node.length >= 2 &&
      typeof node[0] === "number" &&
      typeof node[1] === "number"
    ) {
      return node.map((value) =>
        typeof value === "number"
          ? Number(value.toFixed(COORDINATE_DECIMAL_PLACES))
          : value,
      );
    }
    return node.map(roundCoordinates);
  }
  return node;
}

export async function GET(request: NextRequest) {
  const requestId = newRequestId();

  let query;
  try {
    query = parseMapCatchmentsQuery(
      Object.fromEntries(request.nextUrl.searchParams),
    );
  } catch (error) {
    return errorResponse(
      "BAD_REQUEST",
      error instanceof z.ZodError
        ? error.issues.map((issue) => issue.message).join(" ")
        : "Invalid query parameters.",
      requestId,
    );
  }

  try {
    const [minLon, minLat, maxLon, maxLat] = query.bbox;
    const prisma = getPrismaClient();

    const conditions = [
      Prisma.sql`minimum_latitude <= ${maxLat}`,
      Prisma.sql`maximum_latitude >= ${minLat}`,
      Prisma.sql`minimum_longitude <= ${maxLon}`,
      Prisma.sql`maximum_longitude >= ${minLon}`,
    ];
    if (query.academicYear) {
      conditions.push(Prisma.sql`academic_year = ${query.academicYear}`);
    }
    if (query.areaType) {
      conditions.push(Prisma.sql`area_type = ${query.areaType}`);
    }

    // Ordered by a deterministic hash of the id rather than left to the
    // database's default scan order (effectively arbitrary on CockroachDB).
    // The map now loads every catchment area in one request on page load
    // and never re-fetches on pan/zoom (see school-map.tsx), so this
    // mainly guards against MAX_CATCHMENT_MAP_FEATURES ever being exceeded
    // as coverage keeps growing - if that ever truncates results, a stable
    // hash-ordered subset is still far better than an arbitrary one that
    // could differ between near-identical requests (the flicker this
    // originally fixed).
    const areas = await prisma.$queryRaw<MapCatchmentRow[]>`
      SELECT id, area_name, area_type, academic_year, simplified_geometry_geojson, performance_percentile, performance_metric_code
      FROM catchment_areas
      WHERE ${Prisma.join(conditions, " AND ")}
      ORDER BY md5(id::text)
      LIMIT ${query.limit}
    `;

    const features = [];
    for (const area of areas) {
      let geometry: { type: string; coordinates: unknown };
      try {
        geometry = JSON.parse(area.simplified_geometry_geojson);
      } catch {
        // A single malformed stored geometry should not fail the whole map
        // request; skip it and log for the ingestion team to investigate.
        logger.warn("Skipping catchment area with malformed stored geometry", {
          areaId: area.id,
        });
        continue;
      }
      features.push({
        type: "Feature" as const,
        geometry: {
          type: geometry.type,
          coordinates: roundCoordinates(geometry.coordinates),
        },
        properties: {
          id: area.id,
          areaName: area.area_name,
          areaType: area.area_type,
          academicYear: area.academic_year,
          performancePercentile: area.performance_percentile,
          performanceMetricCode: area.performance_metric_code,
        },
      });
    }

    const featureCollection = { type: "FeatureCollection" as const, features };
    return jsonResponse(featureCollection, {
      requestId,
      // Longer than before: the whole dataset is now identical for every
      // visitor and every viewport (loaded once, not bbox-scoped), so it's
      // effectively static until the next catchment import or score
      // refresh - safe to cache harder both client- and CDN-side.
      cacheControl: "public, max-age=1800, stale-while-revalidate=3600",
    });
  } catch (error) {
    return internalErrorResponse(requestId, "GET /api/map/catchments", error);
  }
}
