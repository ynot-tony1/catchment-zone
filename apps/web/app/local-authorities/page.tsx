import type { Metadata } from "next";
import Link from "next/link";
import {
  parseLocalAuthoritySearchParams,
  type RawSearchParams,
} from "@catchment-zone/shared";
import { z } from "zod";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { searchLocalAuthorities } from "@/lib/queries/local-authorities";
import { safeQuery } from "@/lib/safe-query";

export const metadata: Metadata = {
  title: "Local authorities",
};

function coverageBadgeVariant(
  status: string,
): "success" | "warning" | "secondary" {
  switch (status) {
    case "FULL":
      return "success";
    case "PARTIAL":
    case "PILOT":
      return "warning";
    default:
      return "secondary";
  }
}

function coverageLabel(status: string): string {
  switch (status) {
    case "FULL":
      return "Full catchment coverage";
    case "PARTIAL":
      return "Partial catchment coverage";
    case "PILOT":
      return "Pilot catchment coverage";
    default:
      return "Catchment data not available";
  }
}

export default async function LocalAuthoritiesPage({
  searchParams,
}: {
  searchParams: Promise<RawSearchParams>;
}) {
  const raw = await searchParams;

  let filters;
  try {
    filters = parseLocalAuthoritySearchParams(raw);
  } catch (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Invalid search</AlertTitle>
        <AlertDescription>
          {error instanceof z.ZodError
            ? error.issues.map((issue) => issue.message).join(" ")
            : "Invalid search."}
        </AlertDescription>
      </Alert>
    );
  }

  const result = await safeQuery(
    "local-authorities-search",
    () => searchLocalAuthorities(filters),
    {
      items: [],
      nextCursor: null,
    },
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Local authorities
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Catchment coverage varies by local authority. Only authorities with a
          verified, licensed boundary source show mapped priority areas; the
          rest show as not available rather than a guess.
        </p>
      </div>

      <form method="get" className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="q" className="text-sm font-medium">
            Local authority name
          </label>
          <Input
            id="q"
            name="q"
            defaultValue={filters.q ?? ""}
            placeholder="e.g. Sheffield"
          />
        </div>
        <Button type="submit">Search</Button>
      </form>

      {!result.ok && (
        <Alert variant="warning">
          <AlertTitle>Search temporarily unavailable</AlertTitle>
          <AlertDescription>
            We could not reach the database. Please try again shortly.
          </AlertDescription>
        </Alert>
      )}

      {result.data.items.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Local authority</TableHead>
              <TableHead>Catchment coverage</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.data.items.map((item) => (
              <TableRow key={item.code}>
                <TableCell>
                  <Link
                    href={`/local-authorities/${item.code}`}
                    className="text-primary font-medium underline underline-offset-2"
                  >
                    {item.name}
                  </Link>
                </TableCell>
                <TableCell>
                  <Badge
                    variant={coverageBadgeVariant(item.catchmentCoverageStatus)}
                  >
                    {coverageLabel(item.catchmentCoverageStatus)}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
