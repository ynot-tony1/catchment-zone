import { z } from "zod";
import { CATCHMENT_CHECK_STATUSES } from "../constants";
import { LatitudeSchema, LongitudeSchema } from "./common";

export const CatchmentCheckStatusEnum = z.enum(CATCHMENT_CHECK_STATUSES);

export const CATCHMENT_PHASE_VALUES = ["primary", "secondary"] as const;
export const CatchmentPhaseEnum = z.enum(CATCHMENT_PHASE_VALUES);

/** POST body for /api/catchments/check-point. Exactly one of `postcode` or
 * `point` must be supplied; postcode is resolved server-side via the
 * geocoder and cached in PostcodeCache, point is used as-is (e.g. from a
 * map click). */
export const CatchmentCheckRequestSchema = z
  .object({
    postcode: z.string().trim().min(3).max(10).optional(),
    point: z
      .object({
        lat: LatitudeSchema,
        lon: LongitudeSchema,
      })
      .optional(),
    phase: CatchmentPhaseEnum,
    academicYear: z
      .string()
      .trim()
      .regex(/^\d{4}-\d{4}$/, "academicYear must look like 2025-2026")
      .optional(),
    localAuthorityCode: z.string().trim().min(1).max(10).optional(),
  })
  .refine((v) => Boolean(v.postcode) !== Boolean(v.point), {
    message: "Provide exactly one of postcode or point",
  });
export type CatchmentCheckRequest = z.infer<typeof CatchmentCheckRequestSchema>;

export const CatchmentCheckResultSchema = z.object({
  status: CatchmentCheckStatusEnum,
  disclaimer: z.string(),
  nearBoundaryWarning: z.string().nullable(),
  resolvedPoint: z.object({ lat: z.number(), lon: z.number() }),
  academicYear: z.string(),
  phase: CatchmentPhaseEnum,
  localAuthorityCode: z.string().nullable(),
  localAuthorityName: z.string().nullable(),
  matchedArea: z
    .object({
      id: z.string(),
      areaName: z.string(),
      areaType: z.string(),
    })
    .nullable(),
  servedSchools: z.array(
    z.object({
      urn: z.string(),
      schoolName: z.string(),
    }),
  ),
  distanceToBoundaryMetres: z.number().nullable(),
});
export type CatchmentCheckResult = z.infer<typeof CatchmentCheckResultSchema>;
