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
    // database's default scan order (effectively arbitrary on CockroachDB):
    // catchment areas are the map's primary, always-on layer, and a wide
    // bbox (e.g. the initial /map view, which fits every catchment area in
    // Great Britain) matches far more rows than MAX_MAP_FEATURES. An
    // unordered LIMIT returned a different, geographically arbitrary subset
    // on every near-identical refetch as the user panned, so areas visibly
    // appeared and disappeared even though the viewport barely moved.
    // Hashing the id gives the same representative spread across the
    // matched set every time (the same fix already applied to schools
    // below, for the same reason), but is stable per catchment across
    // requests - panning slightly changes only the areas actually
    // entering/leaving the bbox, not the whole selection.
    const areas = await prisma.$queryRaw<MapCatchmentRow[]>`
      SELECT id, area_name, area_type, academic_year, simplified_geometry_geojson, performance_percentile, performance_metric_code
      FROM catchment_areas
      WHERE ${Prisma.join(conditions, " AND ")}
      ORDER BY md5(id::text)
      LIMIT ${query.limit}
    `;

    const features = [];
    for (const area of areas) {
      let geometry: unknown;
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
        geometry,
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
      cacheControl: "public, max-age=300, stale-while-revalidate=600",
    });
  } catch (error) {
    return internalErrorResponse(requestId, "GET /api/map/catchments", error);
  }
}
