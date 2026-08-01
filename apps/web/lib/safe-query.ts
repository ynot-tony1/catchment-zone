import { logger } from "@/lib/logger";

export type SafeQueryResult<T> =
  { ok: true; data: T } | { ok: false; data: T; unavailable: true };

/**
 * Runs a Prisma-backed query for a Server Component and never lets a
 * database error crash the page. There is no live database in this
 * environment, and even once one exists, a page should degrade to a clear
 * "data unavailable" state rather than a 500, per the product spec's
 * "loading/empty/error states everywhere" requirement.
 *
 * `fallback` is returned (paired with `unavailable: true`) on any error, so
 * callers can render an empty/error state without extra branching for the
 * "what shape is `data` in the failure case" question.
 */
export async function safeQuery<T>(
  label: string,
  fn: () => Promise<T>,
  fallback: T,
): Promise<SafeQueryResult<T>> {
  try {
    const data = await fn();
    return { ok: true, data };
  } catch (error) {
    logger.error("Database query failed", {
      label,
      error:
        error instanceof Error
          ? { name: error.name, message: error.message }
          : String(error),
    });
    return { ok: false, data: fallback, unavailable: true };
  }
}
