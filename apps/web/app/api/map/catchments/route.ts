import { NextRequest } from "next/server";
import { parseMapCatchmentsQuery } from "@schoolscope/shared";
import { z } from "zod";
import { errorResponse, internalErrorResponse, jsonResponse, newRequestId } from "@/lib/api-response";
import { getPrismaClient } from "@/lib/prisma";
import { logger } from "@/lib/logger";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const requestId = newRequestId();

  let query;
  try {
    query = parseMapCatchmentsQuery(Object.fromEntries(request.nextUrl.searchParams));
  } catch (error) {
    return errorResponse(
      "BAD_REQUEST",
      error instanceof z.ZodError ? error.issues.map((issue) => issue.message).join(" ") : "Invalid query parameters.",
      requestId,
    );
  }

  try {
    const [minLon, minLat, maxLon, maxLat] = query.bbox;
    const prisma = getPrismaClient();
    const areas = await prisma.catchmentArea.findMany({
      where: {
        academicYear: query.academicYear,
        areaType: query.areaType,
        minimumLatitude: { lte: maxLat },
        maximumLatitude: { gte: minLat },
        minimumLongitude: { lte: maxLon },
        maximumLongitude: { gte: minLon },
      },
      select: { id: true, areaName: true, areaType: true, academicYear: true, simplifiedGeometryGeojson: true },
      take: query.limit,
    });

    const features = [];
    for (const area of areas) {
      let geometry: unknown;
      try {
        geometry = JSON.parse(area.simplifiedGeometryGeojson);
      } catch {
        // A single malformed stored geometry should not fail the whole map
        // request; skip it and log for the ingestion team to investigate.
        logger.warn("Skipping catchment area with malformed stored geometry", { areaId: area.id });
        continue;
      }
      features.push({
        type: "Feature" as const,
        geometry,
        properties: {
          id: area.id,
          areaName: area.areaName,
          areaType: area.areaType,
          academicYear: area.academicYear,
        },
      });
    }

    const featureCollection = { type: "FeatureCollection" as const, features };
    return jsonResponse(featureCollection, { requestId, cacheControl: "public, max-age=300, stale-while-revalidate=600" });
  } catch (error) {
    return internalErrorResponse(requestId, "GET /api/map/catchments", error);
  }
}
