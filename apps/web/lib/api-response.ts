import { randomUUID } from "node:crypto";
import { NextResponse } from "next/server";
import { logger } from "@/lib/logger";

/** Generates a per-request id used for log correlation and returned to the
 * client via the X-Request-Id response header, never for anything
 * user-identifying. */
export function newRequestId(): string {
  return randomUUID();
}

type JsonInit = {
  status?: number;
  requestId: string;
  cacheControl?: string;
};

/** Builds a JSON response with the standard response envelope headers
 * (request id for correlation, an explicit Cache-Control). Route handlers
 * should use this instead of `NextResponse.json` directly so headers stay
 * consistent across the API surface. */
export function jsonResponse<T>(body: T, init: JsonInit): NextResponse {
  const res = NextResponse.json(body, { status: init.status ?? 200 });
  res.headers.set("X-Request-Id", init.requestId);
  res.headers.set("Cache-Control", init.cacheControl ?? "no-store");
  return res;
}

export type SafeErrorCode =
  | "BAD_REQUEST"
  | "NOT_FOUND"
  | "RATE_LIMITED"
  | "UPSTREAM_UNAVAILABLE"
  | "INTERNAL_ERROR";

const STATUS_BY_CODE: Record<SafeErrorCode, number> = {
  BAD_REQUEST: 400,
  NOT_FOUND: 404,
  RATE_LIMITED: 429,
  UPSTREAM_UNAVAILABLE: 503,
  INTERNAL_ERROR: 500,
};

/** A JSON error body that is always safe to send to the client: a stable
 * machine-readable code, a human message that never includes a raw
 * exception, hostname, connection string, or stack trace, and the request
 * id for support correlation. */
export function errorResponse(
  code: SafeErrorCode,
  message: string,
  requestId: string,
  details?: unknown,
): NextResponse {
  return jsonResponse(
    { error: { code, message, requestId, ...(details ? { details } : {}) } },
    { status: STATUS_BY_CODE[code], requestId, cacheControl: "no-store" },
  );
}

/** Logs the real error server-side (safe to include stack traces in server
 * logs, just never in the HTTP response) and returns a generic envelope
 * for the client. Use this in every route handler's catch block. */
export function internalErrorResponse(
  requestId: string,
  route: string,
  error: unknown,
): NextResponse {
  logger.error("Unhandled route error", {
    requestId,
    route,
    error:
      error instanceof Error
        ? { name: error.name, message: error.message }
        : String(error),
  });
  return errorResponse(
    "INTERNAL_ERROR",
    "Something went wrong handling this request. Please try again.",
    requestId,
  );
}
