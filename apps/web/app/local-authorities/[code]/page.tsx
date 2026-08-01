import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getPrismaClient } from "@/lib/prisma";
import { safeQuery } from "@/lib/safe-query";

export const revalidate = 3600;

async function getLocalAuthority(code: string) {
  const prisma = getPrismaClient();
  return prisma.localAuthority.findUnique({
    where: { code },
    include: {
      schools: {
        where: { status: "OPEN" },
        orderBy: { schoolName: "asc" },
        take: 200,
        select: { urn: true, schoolName: true, phaseName: true, town: true },
      },
      catchmentSources: {
        orderBy: { academicYear: "desc" },
        select: { id: true, academicYear: true, sourceType: true, licence: true, status: true, sourceUrl: true },
      },
    },
  });
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code } = await params;
  const result = await safeQuery("local-authority-detail-metadata", () => getLocalAuthority(code), null);
  if (!result.ok || !result.data) return { title: "Local authority" };
  return { title: result.data.name };
}

export default async function LocalAuthorityDetailPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  const result = await safeQuery("local-authority-detail", () => getLocalAuthority(code), null);

  if (!result.ok) {
    return (
      <Alert variant="warning">
        <AlertTitle>Local authority details temporarily unavailable</AlertTitle>
        <AlertDescription>We could not reach the database. Please try again shortly.</AlertDescription>
      </Alert>
    );
  }

  const la = result.data;
  if (!la) notFound();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-muted-foreground text-sm">
          <Link href="/local-authorities" className="underline underline-offset-2">
            Local authorities
          </Link>{" "}
          / {la.name}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{la.name}</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Admissions</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm">
          {la.admissionsWebsite && (
            <p>
              <a href={la.admissionsWebsite} className="text-primary underline underline-offset-2" rel="noreferrer">
                Official admissions information
              </a>
            </p>
          )}
          {la.officialCatchmentCheckerUrl && (
            <p>
              <a
                href={la.officialCatchmentCheckerUrl}
                className="text-primary underline underline-offset-2"
                rel="noreferrer"
              >
                Official catchment checker
              </a>{" "}
              (always confirm here before applying)
            </p>
          )}
          {!la.admissionsWebsite && !la.officialCatchmentCheckerUrl && (
            <p className="text-muted-foreground">No official admissions links recorded yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Catchment boundary sources</CardTitle>
        </CardHeader>
        <CardContent>
          {la.catchmentSources.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No catchment boundary source is available for this local authority yet.
            </p>
          ) : (
            <ul className="flex flex-col gap-2 text-sm">
              {la.catchmentSources.map((source) => (
                <li key={source.id} className="flex flex-wrap items-center gap-2">
                  <Badge variant={source.status === "VALID" ? "success" : "secondary"}>{source.status}</Badge>
                  <span>{source.sourceType}</span>
                  <span className="text-muted-foreground">
                    {source.academicYear} &middot; {source.licence}
                  </span>
                  <a href={source.sourceUrl} className="text-primary underline underline-offset-2" rel="noreferrer">
                    Source
                  </a>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Schools ({la.schools.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {la.schools.length === 0 ? (
            <p className="text-muted-foreground text-sm">No open schools recorded for this local authority.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>School</TableHead>
                  <TableHead>Phase</TableHead>
                  <TableHead>Town</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {la.schools.map((school) => (
                  <TableRow key={school.urn}>
                    <TableCell>
                      <Link href={`/schools/${school.urn}`} className="text-primary underline underline-offset-2">
                        {school.schoolName}
                      </Link>
                    </TableCell>
                    <TableCell>{school.phaseName}</TableCell>
                    <TableCell>{school.town ?? "Not available"}</TableCell>
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
