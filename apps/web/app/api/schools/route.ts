import { NextRequest } from "next/server";
import { parseSchoolSearchParams } from "@schoolscope/shared";
import { z } from "zod";
import {
  errorResponse,
  internalErrorResponse,
  jsonResponse,
  newRequestId,
} from "@/lib/api-response";
import { searchSchools } from "@/lib/queries/schools";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const requestId = newRequestId();

  let filters;
  try {
    filters = parseSchoolSearchParams(
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
    const result = await searchSchools(filters);
    return jsonResponse(result, {
      requestId,
      cacheControl: "public, max-age=60, stale-while-revalidate=300",
    });
  } catch (error) {
    return internalErrorResponse(requestId, "GET /api/schools", error);
  }
}
