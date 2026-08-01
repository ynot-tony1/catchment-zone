import { z } from "zod";
import { MAX_MAP_FEATURES } from "../constants";
import { BboxQuerySchema, firstValue, splitCsv } from "./common";
import { SchoolStatusEnum } from "./school";
import type { RawSearchParams } from "./school";

export const MapSchoolsQuerySchema = z.object({
  bbox: BboxQuerySchema,
  phaseCode: z.string().trim().min(1).max(20).optional(),
  establishmentTypeCode: z.string().trim().min(1).max(20).optional(),
  trustId: z.string().trim().min(1).max(50).optional(),
  status: z.array(SchoolStatusEnum).optional(),
  limit: z.coerce
    .number()
    .int()
    .min(1)
    .max(MAX_MAP_FEATURES)
    .default(MAX_MAP_FEATURES),
});
export type MapSchoolsQuery = z.infer<typeof MapSchoolsQuerySchema>;

export function parseMapSchoolsQuery(raw: RawSearchParams): MapSchoolsQuery {
  return MapSchoolsQuerySchema.parse({
    bbox: firstValue(raw.bbox),
    phaseCode: firstValue(raw.phaseCode),
    establishmentTypeCode: firstValue(raw.establishmentTypeCode),
    trustId: firstValue(raw.trustId),
    status: splitCsv(raw.status),
    limit: firstValue(raw.limit) ?? String(MAX_MAP_FEATURES),
  });
}

export const MapCatchmentsQuerySchema = z.object({
  bbox: BboxQuerySchema,
  academicYear: z
    .string()
    .trim()
    .regex(/^\d{4}-\d{4}$/)
    .optional(),
  areaType: z.string().trim().min(1).max(30).optional(),
  limit: z.coerce
    .number()
    .int()
    .min(1)
    .max(MAX_MAP_FEATURES)
    .default(MAX_MAP_FEATURES),
});
export type MapCatchmentsQuery = z.infer<typeof MapCatchmentsQuerySchema>;

export function parseMapCatchmentsQuery(
  raw: RawSearchParams,
): MapCatchmentsQuery {
  return MapCatchmentsQuerySchema.parse({
    bbox: firstValue(raw.bbox),
    academicYear: firstValue(raw.academicYear),
    areaType: firstValue(raw.areaType),
    limit: firstValue(raw.limit) ?? String(MAX_MAP_FEATURES),
  });
}
