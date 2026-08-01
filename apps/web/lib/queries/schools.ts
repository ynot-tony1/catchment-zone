import type { Prisma } from "@schoolscope/database";
import { decodeCursor, encodeCursor, type SchoolSearchFilters } from "@schoolscope/shared";
import { boundingBoxAroundPoint, distanceKm } from "@/lib/geo";
import { getPrismaClient } from "@/lib/prisma";

export type SchoolSearchResultItem = {
  urn: string;
  schoolName: string;
  status: string;
  phaseName: string;
  establishmentTypeName: string;
  town: string | null;
  postcode: string | null;
  localAuthorityName: string | null;
  trustName: string | null;
  latitude: number | null;
  longitude: number | null;
  distanceKm: number | null;
};

export type SchoolSearchResult = {
  items: SchoolSearchResultItem[];
  nextCursor: string | null;
};

const SEARCH_SELECT = {
  urn: true,
  schoolName: true,
  status: true,
  phaseName: true,
  establishmentTypeName: true,
  town: true,
  postcode: true,
  latitude: true,
  longitude: true,
  normalisedName: true,
  openingDate: true,
  localAuthority: { select: { name: true } },
  trust: { select: { trustName: true } },
} satisfies Prisma.SchoolSelect;

type SearchRow = Prisma.SchoolGetPayload<{ select: typeof SEARCH_SELECT }>;

function toItem(row: SearchRow, fromPoint: { lat: number; lon: number } | null): SchoolSearchResultItem {
  return {
    urn: row.urn,
    schoolName: row.schoolName,
    status: row.status,
    phaseName: row.phaseName,
    establishmentTypeName: row.establishmentTypeName,
    town: row.town,
    postcode: row.postcode,
    localAuthorityName: row.localAuthority?.name ?? null,
    trustName: row.trust?.trustName ?? null,
    latitude: row.latitude,
    longitude: row.longitude,
    distanceKm:
      fromPoint && row.latitude !== null && row.longitude !== null
        ? distanceKm(fromPoint, { lat: row.latitude, lon: row.longitude })
        : null,
  };
}

function buildWhere(filters: SchoolSearchFilters): Prisma.SchoolWhereInput {
  const where: Prisma.SchoolWhereInput = {
    status: filters.status && filters.status.length > 0 ? { in: filters.status } : "OPEN",
  };

  if (filters.urn) where.urn = filters.urn;
  if (filters.q) where.normalisedName = { contains: filters.q.trim().toLowerCase() };
  if (filters.postcode) where.postcode = { startsWith: filters.postcode.trim().toUpperCase() };
  if (filters.town) where.town = { equals: filters.town, mode: "insensitive" };
  if (filters.localAuthorityCode) where.localAuthorityCode = filters.localAuthorityCode;
  if (filters.regionCode) where.regionCode = filters.regionCode;
  if (filters.phaseCode) where.phaseCode = filters.phaseCode;
  if (filters.establishmentTypeCode) where.establishmentTypeCode = filters.establishmentTypeCode;
  if (filters.trustId) where.trustId = filters.trustId;
  if (filters.gender) where.gender = filters.gender;
  if (filters.religiousCharacter) where.religiousCharacter = filters.religiousCharacter;
  if (filters.hasSenProvision) where.hasSenProvision = true;
  if (filters.urbanRuralCode) where.urbanRuralCode = filters.urbanRuralCode;
  if (filters.academyStatus === "ACADEMY") where.trustId = { not: null };
  if (filters.academyStatus === "MAINTAINED") where.trustId = null;
  if (filters.hasCatchmentData) where.catchmentLinks = { some: {} };
  if (filters.minAge !== undefined) where.maximumAge = { gte: filters.minAge };
  if (filters.maxAge !== undefined) where.minimumAge = { lte: filters.maxAge };

  return where;
}

/**
 * Keyset (not offset) pagination: the cursor encodes the last row's sort key
 * plus its urn as a tiebreaker, so results stay stable even if rows are
 * inserted or removed between page requests, which offset pagination cannot
 * guarantee once ingestion runs regularly against this table.
 */
async function searchByKeyset(filters: SchoolSearchFilters): Promise<SchoolSearchResult> {
  const prisma = getPrismaClient();
  const where = buildWhere(filters);
  const descending = filters.sort === "name_desc" || filters.sort === "opening_date_desc";
  const byOpeningDate = filters.sort === "opening_date_asc" || filters.sort === "opening_date_desc";

  const sortField: "normalisedName" | "openingDate" = byOpeningDate ? "openingDate" : "normalisedName";
  const cursor = filters.cursor ? decodeCursor<{ k: string | number | null; u: string }>(filters.cursor) : null;

  if (cursor) {
    const comparator = descending ? "lt" : "gt";
    const keyCondition: Prisma.SchoolWhereInput =
      cursor.k === null
        ? { [sortField]: descending ? { not: null } : null, urn: { [comparator]: cursor.u } }
        : {
            OR: [
              { [sortField]: { [comparator]: cursor.k } },
              { [sortField]: cursor.k, urn: { [comparator]: cursor.u } },
            ],
          };
    Object.assign(where, { AND: [{ ...where }, keyCondition] });
  }

  const rows = await prisma.school.findMany({
    where,
    select: SEARCH_SELECT,
    orderBy: [{ [sortField]: descending ? "desc" : "asc" }, { urn: descending ? "desc" : "asc" }],
    take: filters.limit + 1,
  });

  const hasMore = rows.length > filters.limit;
  const page = hasMore ? rows.slice(0, filters.limit) : rows;
  const last = page[page.length - 1];
  const nextCursor =
    hasMore && last
      ? encodeCursor({ k: byOpeningDate ? (last.openingDate?.toISOString() ?? null) : last.normalisedName, u: last.urn })
      : null;

  return { items: page.map((row) => toItem(row, null)), nextCursor };
}

/**
 * Distance sort has no database-level ordering to lean on (no PostGIS), so
 * candidates are prefiltered by a bounding-box index scan, then the exact
 * great-circle distance is computed and sorted in memory. The bbox radius
 * cap keeps the candidate set bounded even for a wide radiusKm.
 */
async function searchByDistance(filters: SchoolSearchFilters): Promise<SchoolSearchResult> {
  if (filters.lat === undefined || filters.lon === undefined) {
    throw new Error("searchByDistance requires lat and lon");
  }
  const prisma = getPrismaClient();
  const radiusKm = filters.radiusKm ?? 10;
  const bbox = boundingBoxAroundPoint(filters.lat, filters.lon, radiusKm);
  const where: Prisma.SchoolWhereInput = {
    ...buildWhere(filters),
    latitude: { gte: bbox.minLat, lte: bbox.maxLat },
    longitude: { gte: bbox.minLon, lte: bbox.maxLon },
  };

  const rows = await prisma.school.findMany({ where, select: SEARCH_SELECT, take: 2000 });
  const fromPoint = { lat: filters.lat, lon: filters.lon };
  const items = rows
    .map((row) => toItem(row, fromPoint))
    .filter((item): item is SchoolSearchResultItem & { distanceKm: number } => item.distanceKm !== null && item.distanceKm <= radiusKm)
    .sort((a, b) => a.distanceKm - b.distanceKm || a.urn.localeCompare(b.urn));

  const cursor = filters.cursor ? decodeCursor<{ k: number; u: string }>(filters.cursor) : null;
  const startIndex = cursor
    ? items.findIndex((item) => item.distanceKm > cursor.k || (item.distanceKm === cursor.k && item.urn > cursor.u))
    : 0;
  const page = items.slice(Math.max(startIndex, 0), Math.max(startIndex, 0) + filters.limit);
  const hasMore = Math.max(startIndex, 0) + filters.limit < items.length;
  const last = page[page.length - 1];
  const nextCursor = hasMore && last ? encodeCursor({ k: last.distanceKm, u: last.urn }) : null;

  return { items: page, nextCursor };
}

export async function searchSchools(filters: SchoolSearchFilters): Promise<SchoolSearchResult> {
  if (filters.sort === "distance") return searchByDistance(filters);
  return searchByKeyset(filters);
}
