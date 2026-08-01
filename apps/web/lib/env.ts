import { z } from "zod";
import { UNKNOWN_GIT_SHA } from "@schoolscope/shared";

// Server-only environment variables. This module must never be imported
// from a Client Component; it is read at request time inside route
// handlers and server components. Validation only checks the variables are
// present and well-formed, not that DATABASE_URL points at a reachable
// database (there is no live database in this environment, and `next
// build` must not require one).
const ServerEnvSchema = z.object({
  DATABASE_URL: z.string().min(1, "DATABASE_URL is required"),
  POSTCODE_GEOCODER: z.string().default("postcodes.io"),
  CATCHMENT_BOUNDARY_WARNING_METRES: z.coerce.number().positive().default(75),
  LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
});

let cached: z.infer<typeof ServerEnvSchema> | null = null;

/** Lazily parses and caches server env vars on first use. Deliberately not
 * evaluated at module load, so importing this file never breaks a build
 * that has not set every variable (e.g. static analysis passes). */
export function getServerEnv(): z.infer<typeof ServerEnvSchema> {
  if (cached) return cached;
  cached = ServerEnvSchema.parse({
    DATABASE_URL: process.env.DATABASE_URL,
    POSTCODE_GEOCODER: process.env.POSTCODE_GEOCODER,
    CATCHMENT_BOUNDARY_WARNING_METRES:
      process.env.CATCHMENT_BOUNDARY_WARNING_METRES,
    LOG_LEVEL: process.env.LOG_LEVEL,
  });
  return cached;
}

/** Public (browser-safe) env vars. Only NEXT_PUBLIC_* variables ever reach
 * the client bundle; this accessor documents that boundary in one place
 * rather than reading process.env.NEXT_PUBLIC_* ad hoc across components. */
export function getPublicEnv() {
  return {
    siteUrl: process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
    mapStyleUrl:
      process.env.NEXT_PUBLIC_MAP_STYLE_URL ??
      "https://demotiles.maplibre.org/style.json",
    mapAttribution:
      process.env.NEXT_PUBLIC_MAP_ATTRIBUTION ?? "OpenStreetMap contributors",
  };
}

/** Build-time / deploy-time identifier for /status. Vercel sets
 * VERCEL_GIT_COMMIT_SHA automatically; falls back to "unknown" locally. */
export function getGitSha(): string {
  return (
    process.env.VERCEL_GIT_COMMIT_SHA ?? process.env.GIT_SHA ?? UNKNOWN_GIT_SHA
  );
}
