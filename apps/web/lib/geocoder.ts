import { getPrismaClient } from "@/lib/prisma";
import { logger } from "@/lib/logger";
import { getServerEnv } from "@/lib/env";

const CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

/** Uppercases and strips all whitespace, e.g. "s1 2hh" -> "S12HH". This is
 * the cache key. PostcodeCache is keyed by normalised postcode only (never
 * by user or session), per the product requirement that we cache lookups
 * generically rather than tying any stored data to who submitted it. */
export function normalisePostcode(raw: string): string {
  return raw.toUpperCase().replace(/\s+/g, "");
}

/** Temporary crosswalk from the ONS/GSS local authority code that
 * postcodes.io returns (codes.admin_district) to the DfE local authority
 * code used throughout this schema (LocalAuthority.code, e.g. "373" for
 * Sheffield). There is no bundled ONS<->DfE crosswalk dataset in this
 * project yet, so this only covers the single pilot authority. Extend this
 * map (or replace it with a real ingested crosswalk table) before onboarding
 * another local authority's catchment data. */
const ONS_TO_DFE_LA_CODE: Record<string, string> = {
  E08000019: "373", // Sheffield
};

export type GeocodeResult = {
  lat: number;
  lon: number;
  localAuthorityCode: string | null;
};

/** Resolves a UK postcode to coordinates via the configured geocoder
 * (postcodes.io by default), caching the result server-side by normalised
 * postcode. Returns null if the postcode is not found. Throws only for an
 * unexpected upstream failure (network error, non-404 error status),
 * which callers should translate into a safe 503-style error response. */
export async function geocodePostcode(
  rawPostcode: string,
): Promise<GeocodeResult | null> {
  const normalised = normalisePostcode(rawPostcode);
  const prisma = getPrismaClient();

  const cached = await prisma.postcodeCache.findUnique({
    where: { normalisedPostcode: normalised },
  });
  if (cached && cached.expiresAt > new Date()) {
    return {
      lat: cached.latitude,
      lon: cached.longitude,
      localAuthorityCode: cached.localAuthorityCode,
    };
  }

  const env = getServerEnv();
  if (env.POSTCODE_GEOCODER !== "postcodes.io") {
    // Only one geocoder is implemented. Fail closed rather than silently
    // falling back to a provider that was not actually configured.
    throw new Error(`Unsupported POSTCODE_GEOCODER: ${env.POSTCODE_GEOCODER}`);
  }

  const response = await fetch(
    `https://api.postcodes.io/postcodes/${encodeURIComponent(normalised)}`,
    {
      headers: { Accept: "application/json" },
    },
  );

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`postcodes.io responded with status ${response.status}`);
  }

  const body = (await response.json()) as {
    result?: {
      latitude: number;
      longitude: number;
      codes?: { admin_district?: string };
    };
  };
  if (!body.result) return null;

  const onsCode = body.result.codes?.admin_district;
  const localAuthorityCode = onsCode
    ? (ONS_TO_DFE_LA_CODE[onsCode] ?? null)
    : null;

  const result: GeocodeResult = {
    lat: body.result.latitude,
    lon: body.result.longitude,
    localAuthorityCode,
  };

  try {
    await prisma.postcodeCache.upsert({
      where: { normalisedPostcode: normalised },
      create: {
        normalisedPostcode: normalised,
        latitude: result.lat,
        longitude: result.lon,
        localAuthorityCode: result.localAuthorityCode,
        source: "postcodes.io",
        expiresAt: new Date(Date.now() + CACHE_TTL_MS),
      },
      update: {
        latitude: result.lat,
        longitude: result.lon,
        localAuthorityCode: result.localAuthorityCode,
        source: "postcodes.io",
        fetchedAt: new Date(),
        expiresAt: new Date(Date.now() + CACHE_TTL_MS),
      },
    });
  } catch (error) {
    // A cache-write failure should not fail the lookup itself, the caller
    // already has a good result. Log and continue.
    logger.warn("Failed to write PostcodeCache entry", {
      error: error instanceof Error ? error.message : String(error),
    });
  }

  return result;
}
