import type { Prisma } from "@schoolscope/database";
import {
  decodeCursor,
  encodeCursor,
  type TrustSearchFilters,
} from "@schoolscope/shared";
import { getPrismaClient } from "@/lib/prisma";

export type TrustSearchResultItem = {
  trustId: string;
  trustName: string;
  trustType: string | null;
  openSchoolCount: number;
};

export type TrustSearchResult = {
  items: TrustSearchResultItem[];
  nextCursor: string | null;
};

function buildWhere(
  filters: TrustSearchFilters,
): Prisma.AcademyTrustWhereInput {
  const where: Prisma.AcademyTrustWhereInput = {};
  if (filters.q) where.trustName = { contains: filters.q, mode: "insensitive" };
  if (filters.trustType) where.trustType = filters.trustType;
  return where;
}

export async function searchTrusts(
  filters: TrustSearchFilters,
): Promise<TrustSearchResult> {
  const prisma = getPrismaClient();
  const where = buildWhere(filters);
  const descending =
    filters.sort === "name_desc" || filters.sort === "size_desc";
  const bySize = filters.sort === "size_asc" || filters.sort === "size_desc";
  const sortField: "trustName" | "openSchoolCount" = bySize
    ? "openSchoolCount"
    : "trustName";

  const cursor = filters.cursor
    ? decodeCursor<{ k: string | number; u: string }>(filters.cursor)
    : null;
  if (cursor) {
    const comparator = descending ? "lt" : "gt";
    Object.assign(where, {
      AND: [
        { ...where },
        {
          OR: [
            { [sortField]: { [comparator]: cursor.k } },
            { [sortField]: cursor.k, trustId: { [comparator]: cursor.u } },
          ],
        },
      ],
    });
  }

  const rows = await prisma.academyTrust.findMany({
    where,
    select: {
      trustId: true,
      trustName: true,
      trustType: true,
      openSchoolCount: true,
    },
    orderBy: [
      { [sortField]: descending ? "desc" : "asc" },
      { trustId: descending ? "desc" : "asc" },
    ],
    take: filters.limit + 1,
  });

  const hasMore = rows.length > filters.limit;
  const page = hasMore ? rows.slice(0, filters.limit) : rows;
  const last = page[page.length - 1];
  const nextCursor =
    hasMore && last
      ? encodeCursor({
          k: bySize ? last.openSchoolCount : last.trustName,
          u: last.trustId,
        })
      : null;

  return { items: page, nextCursor };
}
