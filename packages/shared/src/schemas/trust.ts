import { z } from "zod";
import { firstValue } from "./common";
import { NationEnum, type RawSearchParams } from "./school";

export const TRUST_SORT_VALUES = [
  "name_asc",
  "name_desc",
  "size_desc",
  "size_asc",
] as const;
export const TrustSortEnum = z.enum(TRUST_SORT_VALUES);

export const TrustSearchFiltersSchema = z.object({
  q: z.string().trim().min(1).max(200).optional(),
  trustType: z.string().trim().min(1).max(50).optional(),
  sort: TrustSortEnum.default("name_asc"),
  cursor: z.string().trim().min(1).max(500).optional(),
  limit: z.coerce.number().int().min(1).max(100).default(20),
});
export type TrustSearchFilters = z.infer<typeof TrustSearchFiltersSchema>;

export function parseTrustSearchParams(
  raw: RawSearchParams,
): TrustSearchFilters {
  return TrustSearchFiltersSchema.parse({
    q: firstValue(raw.q),
    trustType: firstValue(raw.trustType),
    sort: firstValue(raw.sort) ?? "name_asc",
    cursor: firstValue(raw.cursor),
    limit: firstValue(raw.limit) ?? "20",
  });
}

export const LocalAuthoritySearchFiltersSchema = z.object({
  q: z.string().trim().min(1).max(200).optional(),
  nation: NationEnum.optional(),
  regionCode: z.string().trim().min(1).max(10).optional(),
  catchmentCoverageStatus: z
    .enum(["NOT_AVAILABLE", "PILOT", "PARTIAL", "FULL"])
    .optional(),
  cursor: z.string().trim().min(1).max(500).optional(),
  limit: z.coerce.number().int().min(1).max(100).default(50),
});
export type LocalAuthoritySearchFilters = z.infer<
  typeof LocalAuthoritySearchFiltersSchema
>;

export function parseLocalAuthoritySearchParams(
  raw: RawSearchParams,
): LocalAuthoritySearchFilters {
  return LocalAuthoritySearchFiltersSchema.parse({
    q: firstValue(raw.q),
    nation: firstValue(raw.nation),
    regionCode: firstValue(raw.regionCode),
    catchmentCoverageStatus: firstValue(raw.catchmentCoverageStatus),
    cursor: firstValue(raw.cursor),
    limit: firstValue(raw.limit) ?? "50",
  });
}
