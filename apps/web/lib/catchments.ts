import { getPrismaClient } from "@/lib/prisma";
import { logger } from "@/lib/logger";

export type CatchmentsFeatureCollection = {
  type: "FeatureCollection";
  features: unknown[];
};

const EMPTY_FEATURE_COLLECTION: CatchmentsFeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

// Single source of truth for both the /api/map/catchments route (a plain
// client fetch, kept for programmatic/direct access) and the /map page
// itself (which calls this directly, server-side, to embed the result in
// its initial render - see app/map/page.tsx - rather than making the
// client fetch it after mount, which is what used to leave the map
// visibly blank for several seconds after every page load).
//
// Reads the pre-built map_catchments_cache row (see
// packages/database/prisma/schema.prisma and the ingestor's
// refresh-catchment-overview-cache command) instead of querying and
// transforming all catchment_areas rows on every call - that per-row
// round-trip was the dominant cost in this endpoint, confirmed live
// (forcing response compression barely changed request time, so it
// wasn't a network-transfer problem).
export async function getCatchmentsFeatureCollection(): Promise<CatchmentsFeatureCollection> {
  const prisma = getPrismaClient();
  const cache = await prisma.mapCatchmentsCache.findUnique({
    where: { id: "current" },
  });
  if (!cache) {
    // Not yet populated (a fresh environment before the first
    // refresh-catchment-overview-cache run) - an empty map is the honest
    // result, not an error.
    return EMPTY_FEATURE_COLLECTION;
  }

  try {
    return JSON.parse(
      cache.featureCollectionJson,
    ) as CatchmentsFeatureCollection;
  } catch {
    logger.warn("map_catchments_cache row has malformed JSON, serving empty");
    return EMPTY_FEATURE_COLLECTION;
  }
}
