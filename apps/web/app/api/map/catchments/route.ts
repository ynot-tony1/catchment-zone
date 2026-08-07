import { NextRequest } from "next/server";
import { parseMapCatchmentsQuery } from "@catchment-zone/shared";
import { z } from "zod";
import {
  errorResponse,
  internalErrorResponse,
  jsonResponse,
  newRequestId,
} from "@/lib/api-response";
import { getCatchmentsFeatureCollection } from "@/lib/catchments";

export const runtime = "nodejs";

// The map now always requests the whole of Great Britain in one go (see
// school-map.tsx) and every catchment area fits in the pre-built
// map_catchments_cache row (see lib/catchments.ts), so bbox/academicYear/
// areaType are validated for a well-formed request but no longer used to
// filter - there is only one dataset to serve. Query parsing is kept so
// this route's contract doesn't silently change shape for any other
// caller.
export async function GET(request: NextRequest) {
  const requestId = newRequestId();

  try {
    parseMapCatchmentsQuery(Object.fromEntries(request.nextUrl.searchParams));
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
    const featureCollection = await getCatchmentsFeatureCollection();
    return jsonResponse(featureCollection, {
      requestId,
      // The cache is identical for every visitor and every viewport, and
      // only changes when refresh-catchment-overview-cache is next run
      // (after a catchment import or score refresh) - safe to cache hard
      // both client- and CDN-side.
      cacheControl: "public, max-age=1800, stale-while-revalidate=3600",
    });
  } catch (error) {
    return internalErrorResponse(requestId, "GET /api/map/catchments", error);
  }
}
