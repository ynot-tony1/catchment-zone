import {
  CATCHMENT_DISCLAIMER_TEXT,
  CATCHMENT_NEAR_BOUNDARY_TEXT,
  findCatchmentSource,
  hasAnyCatchmentSourceForLa,
  type CatchmentCheckRequest,
  type CatchmentCheckResult,
  type CatchmentCheckStatus,
} from "@schoolscope/shared";
import { geocodePostcode } from "@/lib/geocoder";
import { getServerEnv } from "@/lib/env";
import { distanceToBoundaryMetres, isPointInGeometry, parseCatchmentGeometry } from "@/lib/geo";
import { getPrismaClient } from "@/lib/prisma";

const PHASE_TO_SOURCE_TYPE: Record<"primary" | "secondary", string> = {
  primary: "primary_catchment",
  secondary: "secondary_catchment",
};

/** The UK academic year (September to August) containing `now`, formatted
 * to match config/catchment-sources.yml's "YYYY-YYYY" convention. Used as
 * the default when a caller does not specify one. */
export function currentAcademicYear(now: Date = new Date()): string {
  const year = now.getUTCFullYear();
  const startYear = now.getUTCMonth() >= 8 ? year : year - 1;
  return `${startYear}-${startYear + 1}`;
}

export type CatchmentCheckOutcome =
  | { ok: true; result: CatchmentCheckResult }
  | { ok: false; error: "POSTCODE_NOT_FOUND" };

/**
 * Resolves a point (from a postcode or a direct lat/lon) against the
 * published catchment boundary for the requested phase and academic year,
 * where one is available. Every branch returns one of the closed set of
 * CatchmentCheckStatus values; there is deliberately no path that can
 * report a guaranteed or eligible outcome.
 */
export async function checkCatchmentPoint(request: CatchmentCheckRequest): Promise<CatchmentCheckOutcome> {
  let point: { lat: number; lon: number };
  let fromPostcode = false;
  let localAuthorityCode = request.localAuthorityCode ?? null;

  if (request.point) {
    point = request.point;
  } else {
    const geocoded = await geocodePostcode(request.postcode as string);
    if (!geocoded) return { ok: false, error: "POSTCODE_NOT_FOUND" };
    point = { lat: geocoded.lat, lon: geocoded.lon };
    fromPostcode = true;
    localAuthorityCode = localAuthorityCode ?? geocoded.localAuthorityCode;
  }

  const academicYear = request.academicYear ?? currentAcademicYear();
  const prisma = getPrismaClient();

  let localAuthorityName: string | null = null;
  if (localAuthorityCode) {
    const la = await prisma.localAuthority.findUnique({
      where: { code: localAuthorityCode },
      select: { name: true },
    });
    localAuthorityName = la?.name ?? null;
  }

  const base = {
    disclaimer: CATCHMENT_DISCLAIMER_TEXT,
    resolvedPoint: point,
    academicYear,
    phase: request.phase,
    localAuthorityCode,
    localAuthorityName,
  };

  const notAvailable = (status: CatchmentCheckStatus): CatchmentCheckOutcome => ({
    ok: true,
    result: {
      ...base,
      status,
      nearBoundaryWarning: null,
      matchedArea: null,
      servedSchools: [],
      distanceToBoundaryMetres: null,
    },
  });

  if (!localAuthorityCode || !hasAnyCatchmentSourceForLa(localAuthorityCode)) {
    return notAvailable("OFFICIAL_BOUNDARY_NOT_AVAILABLE");
  }

  const sourceType = PHASE_TO_SOURCE_TYPE[request.phase];
  if (!findCatchmentSource(localAuthorityCode, academicYear, sourceType)) {
    return notAvailable("ACADEMIC_YEAR_NOT_AVAILABLE");
  }

  // Bounding-box prefilter (indexed columns) before the precise, more
  // expensive point-in-polygon test, same pattern as the map endpoints.
  const candidateAreas = await prisma.catchmentArea.findMany({
    where: {
      academicYear,
      source: { localAuthorityCode, sourceType },
      minimumLatitude: { lte: point.lat },
      maximumLatitude: { gte: point.lat },
      minimumLongitude: { lte: point.lon },
      maximumLongitude: { gte: point.lon },
    },
    include: { schools: { include: { school: { select: { urn: true, schoolName: true } } } } },
  });

  let matched: (typeof candidateAreas)[number] | null = null;
  let boundaryDistanceMetres: number | null = null;
  for (const area of candidateAreas) {
    const geometry = parseCatchmentGeometry(area.geometryGeojson);
    if (!geometry) continue;
    if (isPointInGeometry(point.lat, point.lon, geometry)) {
      matched = area;
      boundaryDistanceMetres = distanceToBoundaryMetres(point.lat, point.lon, geometry);
      break;
    }
  }

  const warningMetres = getServerEnv().CATCHMENT_BOUNDARY_WARNING_METRES;
  const isNearBoundary = fromPostcode && boundaryDistanceMetres !== null && boundaryDistanceMetres < warningMetres;

  const status: CatchmentCheckStatus = matched
    ? isNearBoundary
      ? "POSTCODE_RESULT_NEAR_BOUNDARY"
      : "INSIDE_OFFICIAL_PRIORITY_AREA"
    : "OUTSIDE_OFFICIAL_PRIORITY_AREA";

  return {
    ok: true,
    result: {
      ...base,
      status,
      nearBoundaryWarning: isNearBoundary ? CATCHMENT_NEAR_BOUNDARY_TEXT : null,
      matchedArea: matched ? { id: matched.id, areaName: matched.areaName, areaType: matched.areaType } : null,
      servedSchools: matched
        ? matched.schools.map((link) => ({ urn: link.school.urn, schoolName: link.school.schoolName }))
        : [],
      distanceToBoundaryMetres: boundaryDistanceMetres,
    },
  };
}
