import { z } from "zod";
import {
  coerceBooleanParam,
  firstValue,
  LatitudeSchema,
  LongitudeSchema,
  splitCsv,
} from "./common";

// Mirrors the Prisma `SchoolStatus` enum in packages/database/prisma/schema.prisma.
// Duplicated intentionally rather than imported from the generated Prisma
// client, so this package has no dependency on `prisma generate` having run.
export const SCHOOL_STATUS_VALUES = [
  "OPEN",
  "OPEN_BUT_PROPOSED_TO_CLOSE",
  "PROPOSED_TO_OPEN",
  "CLOSED",
] as const;
export const SchoolStatusEnum = z.enum(SCHOOL_STATUS_VALUES);
export type SchoolStatus = z.infer<typeof SchoolStatusEnum>;

// Mirrors the Prisma `Nation` enum. England is GIAS-sourced; Scotland and
// Wales each have their own official register with its own identifier
// scheme (see services/ingestor/src/catchment_zone_ingestor/adapters/
// scotland.py, wales.py for what's actually verified live for each).
//
// Northern Ireland is deliberately excluded: the only machine-readable
// register found for it has been stale since February 2016 with no newer
// extract available - see PROJECT_STATUS.md.
export const NATION_VALUES = ["ENGLAND", "SCOTLAND", "WALES"] as const;
export const NationEnum = z.enum(NATION_VALUES);
export type Nation = z.infer<typeof NationEnum>;

export const ACADEMY_STATUS_VALUES = ["ACADEMY", "MAINTAINED"] as const;
export const AcademyStatusEnum = z.enum(ACADEMY_STATUS_VALUES);

export const SCHOOL_SORT_VALUES = [
  "name_asc",
  "name_desc",
  "distance",
  "opening_date_desc",
  "opening_date_asc",
] as const;
export const SchoolSortEnum = z.enum(SCHOOL_SORT_VALUES);
export type SchoolSort = z.infer<typeof SchoolSortEnum>;

/** Raw shape of Next.js `searchParams` (values may be repeated). */
export type RawSearchParams = Record<string, string | string[] | undefined>;

export const SchoolSearchFiltersSchema = z
  .object({
    q: z.string().trim().min(1).max(200).optional(),
    // GIAS URNs are numeric, but Scotland's SchUID ("8212627P") is
    // alphanumeric - a numeric-only pattern would silently reject every
    // Scottish school lookup by id.
    urn: z
      .string()
      .trim()
      .regex(/^[A-Za-z0-9]{1,20}$/, "URN must be alphanumeric")
      .optional(),
    postcode: z.string().trim().min(1).max(16).optional(),
    town: z.string().trim().min(1).max(100).optional(),
    nation: NationEnum.optional(),
    localAuthorityCode: z.string().trim().min(1).max(10).optional(),
    regionCode: z.string().trim().min(1).max(10).optional(),
    phaseCode: z.string().trim().min(1).max(20).optional(),
    establishmentTypeCode: z.string().trim().min(1).max(20).optional(),
    status: z.array(SchoolStatusEnum).optional(),
    academyStatus: AcademyStatusEnum.optional(),
    trustId: z.string().trim().min(1).max(50).optional(),
    gender: z.string().trim().min(1).max(30).optional(),
    religiousCharacter: z.string().trim().min(1).max(100).optional(),
    hasSenProvision: z.boolean().optional(),
    minAge: z.coerce.number().int().min(0).max(25).optional(),
    maxAge: z.coerce.number().int().min(0).max(25).optional(),
    urbanRuralCode: z.string().trim().min(1).max(20).optional(),
    hasCatchmentData: z.boolean().optional(),
    lat: LatitudeSchema.optional(),
    lon: LongitudeSchema.optional(),
    radiusKm: z.coerce.number().min(0.1).max(100).optional(),
    sort: SchoolSortEnum.default("name_asc"),
    cursor: z.string().trim().min(1).max(500).optional(),
    limit: z.coerce.number().int().min(1).max(100).default(20),
  })
  .refine(
    (v) =>
      v.sort !== "distance" || (v.lat !== undefined && v.lon !== undefined),
    {
      message: "Sorting by distance requires both lat and lon",
      path: ["sort"],
    },
  )
  .refine((v) => v.lat === undefined || v.lon !== undefined, {
    message: "lat requires lon",
    path: ["lon"],
  })
  .refine(
    (v) =>
      v.minAge === undefined || v.maxAge === undefined || v.minAge <= v.maxAge,
    {
      message: "minAge must be less than or equal to maxAge",
      path: ["minAge"],
    },
  );

export type SchoolSearchFilters = z.infer<typeof SchoolSearchFiltersSchema>;

/** Parses Next.js `searchParams` (or a URLSearchParams-derived record) into
 * validated, typed filters. Throws a ZodError on invalid input; callers in
 * route handlers should catch and return a 400 safe error envelope. */
export function parseSchoolSearchParams(
  raw: RawSearchParams,
): SchoolSearchFilters {
  return SchoolSearchFiltersSchema.parse({
    q: firstValue(raw.q),
    urn: firstValue(raw.urn),
    postcode: firstValue(raw.postcode),
    town: firstValue(raw.town),
    nation: firstValue(raw.nation),
    localAuthorityCode: firstValue(raw.localAuthorityCode ?? raw.la),
    regionCode: firstValue(raw.regionCode ?? raw.region),
    phaseCode: firstValue(raw.phaseCode ?? raw.phase),
    establishmentTypeCode: firstValue(raw.establishmentTypeCode ?? raw.type),
    status: splitCsv(raw.status),
    academyStatus: firstValue(raw.academyStatus),
    trustId: firstValue(raw.trustId),
    gender: firstValue(raw.gender),
    religiousCharacter: firstValue(raw.religiousCharacter),
    hasSenProvision: coerceBooleanParam.parse(firstValue(raw.hasSenProvision)),
    minAge: firstValue(raw.minAge),
    maxAge: firstValue(raw.maxAge),
    urbanRuralCode: firstValue(raw.urbanRuralCode),
    hasCatchmentData: coerceBooleanParam.parse(
      firstValue(raw.hasCatchmentData),
    ),
    lat: firstValue(raw.lat),
    lon: firstValue(raw.lon),
    radiusKm: firstValue(raw.radiusKm),
    sort: firstValue(raw.sort) ?? "name_asc",
    cursor: firstValue(raw.cursor),
    limit: firstValue(raw.limit) ?? "20",
  });
}

/** Serialises filters back into a URLSearchParams instance, dropping
 * defaults so the URL stays clean (e.g. no `?sort=name_asc&limit=20` for
 * the default view). Round-trips with parseSchoolSearchParams. */
export function schoolFiltersToSearchParams(
  filters: Partial<SchoolSearchFilters>,
): URLSearchParams {
  const params = new URLSearchParams();
  const set = (key: string, value: unknown) => {
    if (value === undefined || value === null || value === "") return;
    if (Array.isArray(value)) {
      if (value.length === 0) return;
      params.set(key, value.join(","));
      return;
    }
    params.set(key, String(value));
  };

  set("q", filters.q);
  set("urn", filters.urn);
  set("postcode", filters.postcode);
  set("town", filters.town);
  set("nation", filters.nation);
  set("localAuthorityCode", filters.localAuthorityCode);
  set("regionCode", filters.regionCode);
  set("phaseCode", filters.phaseCode);
  set("establishmentTypeCode", filters.establishmentTypeCode);
  set("status", filters.status);
  set("academyStatus", filters.academyStatus);
  set("trustId", filters.trustId);
  set("gender", filters.gender);
  set("religiousCharacter", filters.religiousCharacter);
  if (filters.hasSenProvision) set("hasSenProvision", "true");
  set("minAge", filters.minAge);
  set("maxAge", filters.maxAge);
  set("urbanRuralCode", filters.urbanRuralCode);
  if (filters.hasCatchmentData) set("hasCatchmentData", "true");
  set("lat", filters.lat);
  set("lon", filters.lon);
  set("radiusKm", filters.radiusKm);
  if (filters.sort && filters.sort !== "name_asc") set("sort", filters.sort);
  set("cursor", filters.cursor);
  if (filters.limit && filters.limit !== 20) set("limit", filters.limit);

  return params;
}
