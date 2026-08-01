import { NextRequest } from "next/server";
import { CatchmentCheckRequestSchema } from "@schoolscope/shared";
import { z } from "zod";
import {
  errorResponse,
  internalErrorResponse,
  jsonResponse,
  newRequestId,
} from "@/lib/api-response";
import { checkCatchmentPoint } from "@/lib/queries/catchments";
import { checkRateLimit, rateLimitKeyFromHeaders } from "@/lib/rate-limit";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const requestId = newRequestId();

  const rateLimitKey = rateLimitKeyFromHeaders(request.headers);
  const rateLimit = checkRateLimit(rateLimitKey);
  if (!rateLimit.allowed) {
    const res = errorResponse(
      "RATE_LIMITED",
      "Too many catchment checks. Please wait before trying again.",
      requestId,
    );
    res.headers.set("Retry-After", String(rateLimit.retryAfterSeconds));
    return res;
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return errorResponse(
      "BAD_REQUEST",
      "Request body must be valid JSON.",
      requestId,
    );
  }

  const parsed = CatchmentCheckRequestSchema.safeParse(body);
  if (!parsed.success) {
    return errorResponse(
      "BAD_REQUEST",
      parsed.error instanceof z.ZodError
        ? parsed.error.issues.map((issue) => issue.message).join(" ")
        : "Invalid request.",
      requestId,
    );
  }

  try {
    const outcome = await checkCatchmentPoint(parsed.data);
    if (!outcome.ok) {
      return errorResponse(
        "NOT_FOUND",
        "That postcode could not be found. Check it and try again.",
        requestId,
      );
    }
    return jsonResponse(outcome.result, { requestId });
  } catch (error) {
    return internalErrorResponse(
      requestId,
      "POST /api/admissions/check",
      error,
    );
  }
}
