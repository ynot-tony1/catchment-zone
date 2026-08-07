import { NextRequest } from "next/server";
import { Prisma } from "@catchment-zone/database";
import { parseMapSchoolsQuery } from "@catchment-zone/shared";
import { z } from "zod";
import {
  errorResponse,
  internalErrorResponse,
  jsonResponse,
  newRequestId,
} from "@/lib/api-response";
import { getPrismaClient } from "@/lib/prisma";

export const runtime = "nodejs";

type MapSchoolRow = {
  urn: string;
  nation: string;
  school_name: string;
  phase_name: string;
  status: string;
  latitude: number;
  longitude: number;
  source_extract_date: Date | null;
};

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

    const conditions = [
      Prisma.sql`status IN (${Prisma.join(query.status && query.status.length > 0 ? query.status : ["OPEN"])})`,
      Prisma.sql`latitude BETWEEN ${minLat} AND ${maxLat}`,
      Prisma.sql`longitude BETWEEN ${minLon} AND ${maxLon}`,
      Prisma.sql`latitude IS NOT NULL`,
      Prisma.sql`longitude IS NOT NULL`,
    ];
    if (query.phaseCode) {
      conditions.push(Prisma.sql`phase_code = ${query.phaseCode}`);
    }
    if (query.establishmentTypeCode) {
      conditions.push(
        Prisma.sql`establishment_type_code = ${query.establishmentTypeCode}`,
      );
    }
    if (query.trustId) {
      conditions.push(Prisma.sql`trust_id = ${query.trustId}`);
    }

    // Ordered by a deterministic hash of the URN rather than left to the
    // database's default scan order: a wide bbox (e.g. the initial /map
    // view, which fits all of Great Britain) can match far more rows than
    // MAX_MAP_FEATURES, and an arbitrary/unordered LIMIT consistently
    // returned an unrepresentative one-region cluster instead of a spread
    // across the whole viewport (verified live: default order surfaced
    // almost only Scotland). A plain ORDER BY random() fixed the spread but
    // re-shuffled on every single fetch, so pins visibly appeared and
    // disappeared as the user panned even when the viewport barely moved -
    // hashing the URN gives the same representative spread but is stable
    // per school across requests (the same fix applied to catchment areas
    // in the sibling /api/map/catchments route, for the same reason).
    const schools = await prisma.$queryRaw<MapSchoolRow[]>`
      SELECT urn, nation, school_name, phase_name, status, latitude, longitude, source_extract_date
      FROM schools
      WHERE ${Prisma.join(conditions, " AND ")}
      ORDER BY md5(urn)
      LIMIT ${query.limit}
    `;

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
          nation: school.nation,
          schoolName: school.school_name,
          phaseName: school.phase_name,
          status: school.status,
          sourceExtractDate: school.source_extract_date?.toISOString() ?? null,
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
