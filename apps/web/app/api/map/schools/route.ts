import { NextRequest } from "next/server";
import { parseMapSchoolsQuery } from "@schoolscope/shared";
import { z } from "zod";
import {
  errorResponse,
  internalErrorResponse,
  jsonResponse,
  newRequestId,
} from "@/lib/api-response";
import { getPrismaClient } from "@/lib/prisma";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const requestId = newRequestId();

  let query;
  try {
    query = parseMapSchoolsQuery(
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
    const schools = await prisma.school.findMany({
      where: {
        status:
          query.status && query.status.length > 0
            ? { in: query.status }
            : "OPEN",
        phaseCode: query.phaseCode,
        establishmentTypeCode: query.establishmentTypeCode,
        trustId: query.trustId,
        latitude: { gte: minLat, lte: maxLat, not: null },
        longitude: { gte: minLon, lte: maxLon, not: null },
      },
      select: {
        urn: true,
        schoolName: true,
        phaseName: true,
        status: true,
        latitude: true,
        longitude: true,
      },
      take: query.limit,
    });

    const featureCollection = {
      type: "FeatureCollection" as const,
      features: schools.map((school) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [school.longitude, school.latitude],
        },
        properties: {
          urn: school.urn,
          schoolName: school.schoolName,
          phaseName: school.phaseName,
          status: school.status,
        },
      })),
    };

    return jsonResponse(featureCollection, {
      requestId,
      cacheControl: "public, max-age=60, stale-while-revalidate=300",
    });
  } catch (error) {
    return internalErrorResponse(requestId, "GET /api/map/schools", error);
  }
}
