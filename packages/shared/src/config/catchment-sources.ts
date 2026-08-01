import { z } from "zod";
import raw from "../generated/catchment-sources.json";

// Mirrors config/catchment-sources.yml. This is the single source of truth
// for "which local authorities actually have catchment data loaded", used
// by both the /admissions explorer (to explain OFFICIAL_BOUNDARY_NOT_AVAILABLE
// results honestly) and the /about/data methodology page (coverage summary).
const CatchmentSourceEntrySchema = z.object({
  local_authority_code: z.string(),
  local_authority_name: z.string(),
  academic_year: z.string(),
  source_type: z.string(),
  source_url: z.string(),
  download_url: z.string(),
  format: z.string(),
  coordinate_reference_system: z.string(),
  licence: z.string(),
  last_verified_at: z.string(),
  parser_name: z.string(),
  enabled: z.boolean(),
  notes: z.string().optional(),
});

const CatchmentCandidateSchema = z.object({
  local_authority_name: z.string(),
  reason_not_enabled: z.string(),
});

const CatchmentSourcesFileSchema = z.object({
  sources: z.array(CatchmentSourceEntrySchema),
  candidates: z.array(CatchmentCandidateSchema).default([]),
});

export type CatchmentSourceEntry = z.infer<typeof CatchmentSourceEntrySchema>;
export type CatchmentCandidate = z.infer<typeof CatchmentCandidateSchema>;

const parsed = CatchmentSourcesFileSchema.parse(raw);

/** All configured catchment sources, enabled or not. */
export function listCatchmentSources(): CatchmentSourceEntry[] {
  return parsed.sources;
}

/** Only the sources the ingestor is actually configured to pull. */
export function listEnabledCatchmentSources(): CatchmentSourceEntry[] {
  return parsed.sources.filter((s) => s.enabled);
}

/** Local authorities identified as candidates for a future pilot expansion,
 * but not yet verified/enabled. Shown on /about/data for transparency. */
export function listCatchmentCandidates(): CatchmentCandidate[] {
  return parsed.candidates;
}

/** Distinct local authority codes with at least one enabled catchment
 * source, regardless of academic year or primary/secondary phase. */
export function getPilotLocalAuthorityCodes(): string[] {
  return Array.from(
    new Set(listEnabledCatchmentSources().map((s) => s.local_authority_code)),
  );
}

/** Whether a given local authority + academic year combination has an
 * enabled catchment source for the given source type ("primary_catchment"
 * or "secondary_catchment"). Used to decide between
 * OFFICIAL_BOUNDARY_NOT_AVAILABLE and ACADEMIC_YEAR_NOT_AVAILABLE. */
export function findCatchmentSource(
  localAuthorityCode: string,
  academicYear: string,
  sourceType?: string,
): CatchmentSourceEntry | undefined {
  return listEnabledCatchmentSources().find(
    (s) =>
      s.local_authority_code === localAuthorityCode &&
      s.academic_year === academicYear &&
      (sourceType === undefined || s.source_type === sourceType),
  );
}

/** Whether any enabled source exists for a local authority, in any academic
 * year. Used to distinguish "we have never covered this LA" from "we cover
 * this LA but not this particular academic year". */
export function hasAnyCatchmentSourceForLa(
  localAuthorityCode: string,
): boolean {
  return listEnabledCatchmentSources().some(
    (s) => s.local_authority_code === localAuthorityCode,
  );
}
