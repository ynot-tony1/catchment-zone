import type { Prisma } from "@schoolscope/database";
import { decodeCursor, encodeCursor, type LocalAuthoritySearchFilters } from "@schoolscope/shared";
import { getPrismaClient } from "@/lib/prisma";

export type LocalAuthoritySearchResultItem = {
  code: string;
  name: string;
  regionCode: string | null;
  catchmentCoverageStatus: string;
};

export type LocalAuthoritySearchResult = {
  items: LocalAuthoritySearchResultItem[];
  nextCursor: string | null;
};

function buildWhere(filters: LocalAuthoritySearchFilters): Prisma.LocalAuthorityWhereInput {
  const where: Prisma.LocalAuthorityWhereInput = {};
  if (filters.q) where.name = { contains: filters.q, mode: "insensitive" };
  if (filters.regionCode) where.regionCode = filters.regionCode;
  if (filters.catchmentCoverageStatus) where.catchmentCoverageStatus = filters.catchmentCoverageStatus;
  return where;
}

export async function searchLocalAuthorities(
  filters: LocalAuthoritySearchFilters,
): Promise<LocalAuthoritySearchResult> {
  const prisma = getPrismaClient();
  const where = buildWhere(filters);

  const cursor = filters.cursor ? decodeCursor<{ k: string; u: string }>(filters.cursor) : null;
  if (cursor) {
    Object.assign(where, {
      AND: [
        { ...where },
        { OR: [{ name: { gt: cursor.k } }, { name: cursor.k, code: { gt: cursor.u } }] },
      ],
    });
  }

  const rows = await prisma.localAuthority.findMany({
    where,
    select: { code: true, name: true, regionCode: true, catchmentCoverageStatus: true },
    orderBy: [{ name: "asc" }, { code: "asc" }],
    take: filters.limit + 1,
  });

  const hasMore = rows.length > filters.limit;
  const page = hasMore ? rows.slice(0, filters.limit) : rows;
  const last = page[page.length - 1];
  const nextCursor = hasMore && last ? encodeCursor({ k: last.name, u: last.code }) : null;

  return { items: page, nextCursor };
}
