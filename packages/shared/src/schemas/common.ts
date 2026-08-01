import { z } from "zod";
import { DEFAULT_PAGE_SIZE, MAX_BBOX_AREA_DEGREES, MAX_PAGE_SIZE } from "../constants";

/**
 * Next.js server components and route handlers hand us search params as
 * `string | string[] | undefined`. These helpers normalise that into the
 * single values our Zod schemas expect, so the same schema works whether
 * the caller passed one query param or repeated it.
 */
export function firstValue(value: string | string[] | undefined | null): string | undefined {
  if (value === undefined || value === null) return undefined;
  return Array.isArray(value) ? value[0] : value;
}

export function splitCsv(value: string | string[] | undefined | null): string[] | undefined {
  const v = firstValue(value);
  if (v === undefined || v === "") return undefined;
  return v
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

/** Coerces a raw search-param value to boolean. Accepts "true"/"false"/"1"/"0". */
export const coerceBooleanParam = z
  .union([z.literal("true"), z.literal("false"), z.literal("1"), z.literal("0")])
  .transform((v) => v === "true" || v === "1")
  .optional();

export const PaginationSchema = z.object({
  cursor: z.string().trim().min(1).max(500).optional(),
  limit: z.coerce.number().int().min(1).max(MAX_PAGE_SIZE).default(DEFAULT_PAGE_SIZE),
});
export type Pagination = z.infer<typeof PaginationSchema>;

/** Opaque keyset pagination cursor: base64url-encoded JSON of the last row's
 * sort key(s). Never a raw offset, so pages stay stable as new schools are
 * ingested between requests. */
export function encodeCursor(payload: Record<string, string | number | null>): string {
  return Buffer.from(JSON.stringify(payload), "utf-8").toString("base64url");
}

export function decodeCursor<T = Record<string, string | number | null>>(
  cursor: string,
): T | null {
  try {
    return JSON.parse(Buffer.from(cursor, "base64url").toString("utf-8")) as T;
  } catch {
    return null;
  }
}

export const LatitudeSchema = z.coerce.number().min(-90).max(90);
export const LongitudeSchema = z.coerce.number().min(-180).max(180);

export const PointSchema = z.object({
  lat: LatitudeSchema,
  lon: LongitudeSchema,
});
export type Point = z.infer<typeof PointSchema>;

/** [minLon, minLat, maxLon, maxLat], the standard bbox ordering used by
 * MapLibre's `map.getBounds()` and most GIS tooling. */
export const BboxSchema = z
  .tuple([LongitudeSchema, LatitudeSchema, LongitudeSchema, LatitudeSchema])
  .refine(([minLon, , maxLon]) => minLon < maxLon, {
    message: "minLon must be less than maxLon",
  })
  .refine(([, minLat, , maxLat]) => minLat < maxLat, {
    message: "minLat must be less than maxLat",
  })
  .refine(
    ([minLon, minLat, maxLon, maxLat]) => (maxLon - minLon) * (maxLat - minLat) <= MAX_BBOX_AREA_DEGREES,
    { message: `bbox area exceeds the maximum of ${MAX_BBOX_AREA_DEGREES} square degrees` },
  );
export type Bbox = z.infer<typeof BboxSchema>;

/** Parses a "minLon,minLat,maxLon,maxLat" query-string bbox param. */
export const BboxQuerySchema = z
  .string()
  .transform((s) => s.split(",").map((n) => Number(n.trim())))
  .pipe(BboxSchema);
