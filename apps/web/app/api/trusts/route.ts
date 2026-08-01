import { NextRequest } from "next/server";
import { parseTrustSearchParams } from "@schoolscope/shared";
import { z } from "zod";
import { errorResponse, internalErrorResponse, jsonResponse, newRequestId } from "@/lib/api-response";
import { searchTrusts } from "@/lib/queries/trusts";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const requestId = newRequestId();

  let filters;
  try {
    filters = parseTrustSearchParams(Object.fromEntries(request.nextUrl.searchParams));
  } catch (error) {
    return errorResponse(
      "BAD_REQUEST",
      error instanceof z.ZodError ? error.issues.map((issue) => issue.message).join(" ") : "Invalid query parameters.",
      requestId,
    );
  }

  try {
    const result = await searchTrusts(filters);
    return jsonResponse(result, { requestId, cacheControl: "public, max-age=300, stale-while-revalidate=600" });
  } catch (error) {
    return internalErrorResponse(requestId, "GET /api/trusts", error);
  }
}
