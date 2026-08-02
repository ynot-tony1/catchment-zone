import type { Metadata } from "next";
import Link from "next/link";
import {
  NATION_VALUES,
  SCHOOL_STATUS_VALUES,
  parseSchoolSearchParams,
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
import {
  formatSchoolStatus,
  formatDistanceMetres,
  formatNation,
} from "@/lib/format";
import { searchSchools } from "@/lib/queries/schools";
import { safeQuery } from "@/lib/safe-query";

export const metadata: Metadata = {
  title: "Search schools",
};

function statusBadgeVariant(
  status: string,
): "success" | "warning" | "destructive" | "secondary" {
  switch (status) {
    case "OPEN":
      return "success";
    case "OPEN_BUT_PROPOSED_TO_CLOSE":
      return "warning";
    case "CLOSED":
      return "destructive";
    default:
      return "secondary";
  }
}

export default async function SchoolsPage({
  searchParams,
}: {
  searchParams: Promise<RawSearchParams>;
}) {
  const raw = await searchParams;

  let filters;
  try {
    filters = parseSchoolSearchParams(raw);
  } catch (error) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-semibold">Search schools</h1>
        <Alert variant="destructive">
          <AlertTitle>Invalid search</AlertTitle>
          <AlertDescription>
            {error instanceof z.ZodError
              ? error.issues.map((issue) => issue.message).join(" ")
              : "One or more search parameters could not be understood."}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const result = await safeQuery(
    "schools-search",
    () => searchSchools(filters),
    {
      items: [],
      nextCursor: null,
    },
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Search schools
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Filter open schools by name, location, phase and admissions type.
        </p>
      </div>

      <form method="get" className="grid gap-3 sm:grid-cols-4">
        <div className="sm:col-span-2">
          <label htmlFor="q" className="text-sm font-medium">
            School name
          </label>
          <Input
            id="q"
            name="q"
            defaultValue={filters.q ?? ""}
            placeholder="e.g. Park View Academy"
          />
        </div>
        <div>
          <label htmlFor="postcode" className="text-sm font-medium">
            Postcode
          </label>
          <Input
            id="postcode"
            name="postcode"
            defaultValue={filters.postcode ?? ""}
            placeholder="e.g. S1"
          />
        </div>
        <div>
          <label htmlFor="status" className="text-sm font-medium">
            Status
          </label>
          <select
            id="status"
            name="status"
            defaultValue={filters.status?.[0] ?? "OPEN"}
            className="border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm"
          >
            {SCHOOL_STATUS_VALUES.map((value) => (
              <option key={value} value={value}>
                {formatSchoolStatus(value)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="nation" className="text-sm font-medium">
            Nation
          </label>
          <select
            id="nation"
            name="nation"
            defaultValue={filters.nation ?? ""}
            className="border-input h-9 w-full rounded-md border bg-transparent px-3 text-sm"
          >
            <option value="">All nations</option>
            {NATION_VALUES.map((value) => (
              <option key={value} value={value}>
                {formatNation(value)}
              </option>
            ))}
          </select>
        </div>
        <div className="sm:col-span-4">
          <Button type="submit">Search</Button>
        </div>
      </form>

      {!result.ok && (
        <Alert variant="warning">
          <AlertTitle>Search temporarily unavailable</AlertTitle>
          <AlertDescription>
            We could not reach the database for this search. Please try again
            shortly.
          </AlertDescription>
        </Alert>
      )}

      {result.ok && result.data.items.length === 0 && (
        <Alert>
          <AlertTitle>No schools found</AlertTitle>
          <AlertDescription>
            Try widening your search, for example by clearing the postcode
            filter.
          </AlertDescription>
        </Alert>
      )}

      {result.data.items.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>School</TableHead>
              <TableHead>Nation</TableHead>
              <TableHead>Phase</TableHead>
              <TableHead>Local authority</TableHead>
              <TableHead>Status</TableHead>
              {filters.sort === "distance" && <TableHead>Distance</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.data.items.map((item) => (
              <TableRow key={item.urn}>
                <TableCell>
                  <Link
                    href={`/schools/${item.urn}`}
                    className="text-primary font-medium underline underline-offset-2"
                  >
                    {item.schoolName}
                  </Link>
                  <div className="text-muted-foreground text-xs">
                    {item.town ?? item.postcode ?? ""}
                  </div>
                </TableCell>
                <TableCell>
                  {formatNation(item.nation)}
                  {item.sourceExtractDate && (
                    <Badge variant="outline" className="ml-2">
                      Not live data
                    </Badge>
                  )}
                </TableCell>
                <TableCell>{item.phaseName}</TableCell>
                <TableCell>
                  {item.localAuthorityName ?? "Not available"}
                </TableCell>
                <TableCell>
                  <Badge variant={statusBadgeVariant(item.status)}>
                    {formatSchoolStatus(item.status)}
                  </Badge>
                </TableCell>
                {filters.sort === "distance" && (
                  <TableCell>
                    {item.distanceKm !== null
                      ? formatDistanceMetres(item.distanceKm * 1000)
                      : "Not available"}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
