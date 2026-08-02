import type { Metadata } from "next";
import Link from "next/link";
import {
  parseTrustSearchParams,
  type RawSearchParams,
} from "@catchment-zone/shared";
import { z } from "zod";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { formatNumber } from "@/lib/format";
import { searchTrusts } from "@/lib/queries/trusts";
import { safeQuery } from "@/lib/safe-query";

export const metadata: Metadata = {
  title: "Academy trusts",
};

export default async function TrustsPage({
  searchParams,
}: {
  searchParams: Promise<RawSearchParams>;
}) {
  const raw = await searchParams;

  let filters;
  try {
    filters = parseTrustSearchParams(raw);
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

  const result = await safeQuery("trusts-search", () => searchTrusts(filters), {
    items: [],
    nextCursor: null,
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Academy trusts
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Browse multi-academy and single-academy trusts and the schools they
          run.
        </p>
      </div>

      <form method="get" className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="q" className="text-sm font-medium">
            Trust name
          </label>
          <Input
            id="q"
            name="q"
            defaultValue={filters.q ?? ""}
            placeholder="e.g. Star Academies"
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

      {result.ok && result.data.items.length === 0 && (
        <Alert>
          <AlertTitle>No trusts found</AlertTitle>
          <AlertDescription>Try a different search term.</AlertDescription>
        </Alert>
      )}

      {result.data.items.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Trust</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Open schools</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.data.items.map((item) => (
              <TableRow key={item.trustId}>
                <TableCell>
                  <Link
                    href={`/trusts/${item.trustId}`}
                    className="text-primary font-medium underline underline-offset-2"
                  >
                    {item.trustName}
                  </Link>
                </TableCell>
                <TableCell>{item.trustType ?? "Not available"}</TableCell>
                <TableCell>{formatNumber(item.openSchoolCount)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
