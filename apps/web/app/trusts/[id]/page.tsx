import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatSchoolStatus } from "@/lib/format";
import { getPrismaClient } from "@/lib/prisma";
import { safeQuery } from "@/lib/safe-query";

export const revalidate = 3600;

async function getTrust(trustId: string) {
  const prisma = getPrismaClient();
  return prisma.academyTrust.findUnique({
    where: { trustId },
    include: {
      schools: {
        where: { status: "OPEN" },
        orderBy: { schoolName: "asc" },
        select: {
          urn: true,
          schoolName: true,
          phaseName: true,
          town: true,
          status: true,
        },
      },
    },
  });
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const result = await safeQuery(
    "trust-detail-metadata",
    () => getTrust(id),
    null,
  );
  if (!result.ok || !result.data) return { title: "Academy trust" };
  return { title: result.data.trustName };
}

export default async function TrustDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await safeQuery("trust-detail", () => getTrust(id), null);

  if (!result.ok) {
    return (
      <Alert variant="warning">
        <AlertTitle>Trust details temporarily unavailable</AlertTitle>
        <AlertDescription>
          We could not reach the database. Please try again shortly.
        </AlertDescription>
      </Alert>
    );
  }

  const trust = result.data;
  if (!trust) notFound();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-muted-foreground text-sm">
          <Link href="/trusts" className="underline underline-offset-2">
            Academy trusts
          </Link>{" "}
          / {trust.trustName}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">
          {trust.trustName}
        </h1>
        {trust.trustType && (
          <Badge variant="secondary" className="mt-2">
            {trust.trustType}
          </Badge>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground text-xs">Address</dt>
            <dd>
              {[trust.address, trust.postcode].filter(Boolean).join(", ") ||
                "Not available"}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground text-xs">
              Companies House number
            </dt>
            <dd>{trust.companiesHouseNumber ?? "Not available"}</dd>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Schools in this trust ({trust.schools.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {trust.schools.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No open schools recorded for this trust.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>School</TableHead>
                  <TableHead>Phase</TableHead>
                  <TableHead>Town</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trust.schools.map((school) => (
                  <TableRow key={school.urn}>
                    <TableCell>
                      <Link
                        href={`/schools/${school.urn}`}
                        className="text-primary underline underline-offset-2"
                      >
                        {school.schoolName}
                      </Link>
                    </TableCell>
                    <TableCell>{school.phaseName}</TableCell>
                    <TableCell>{school.town ?? "Not available"}</TableCell>
                    <TableCell>{formatSchoolStatus(school.status)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
