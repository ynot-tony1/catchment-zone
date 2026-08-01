import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getMetricDefinition } from "@schoolscope/shared";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDate, formatMetricValue, formatSchoolStatus } from "@/lib/format";
import { getPrismaClient } from "@/lib/prisma";
import { safeQuery } from "@/lib/safe-query";

export const revalidate = 3600;

async function getSchool(urn: string) {
  const prisma = getPrismaClient();
  return prisma.school.findUnique({
    where: { urn },
    include: {
      localAuthority: true,
      trust: true,
      metrics: { orderBy: { academicYear: "desc" }, take: 50 },
    },
  });
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ urn: string }>;
}): Promise<Metadata> {
  const { urn } = await params;
  const result = await safeQuery("school-detail-metadata", () => getSchool(urn), null);
  if (!result.ok || !result.data) return { title: "School" };
  return { title: result.data.schoolName };
}

export default async function SchoolDetailPage({
  params,
}: {
  params: Promise<{ urn: string }>;
}) {
  const { urn } = await params;
  const result = await safeQuery("school-detail", () => getSchool(urn), null);

  if (!result.ok) {
    return (
      <Alert variant="warning">
        <AlertTitle>School details temporarily unavailable</AlertTitle>
        <AlertDescription>We could not reach the database. Please try again shortly.</AlertDescription>
      </Alert>
    );
  }

  const school = result.data;
  if (!school) notFound();

  const latestMetricsByCode = new Map<string, (typeof school.metrics)[number]>();
  for (const metric of school.metrics) {
    if (!latestMetricsByCode.has(metric.metricCode)) latestMetricsByCode.set(metric.metricCode, metric);
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-muted-foreground text-sm">
          <Link href="/schools" className="underline underline-offset-2">
            Schools
          </Link>{" "}
          / {school.schoolName}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{school.schoolName}</h1>
          <Badge variant={school.status === "OPEN" ? "success" : "secondary"}>
            {formatSchoolStatus(school.status)}
          </Badge>
        </div>
        <p className="text-muted-foreground mt-1 text-sm">
          {school.establishmentTypeName} &middot; {school.phaseName} &middot; URN {school.urn}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            <DetailRow label="Address">
              {[school.street, school.locality, school.town, school.county, school.postcode]
                .filter(Boolean)
                .join(", ") || "Not available"}
            </DetailRow>
            <DetailRow label="Local authority">
              {school.localAuthority ? (
                <Link href={`/local-authorities/${school.localAuthority.code}`} className="text-primary underline underline-offset-2">
                  {school.localAuthority.name}
                </Link>
              ) : (
                "Not available"
              )}
            </DetailRow>
            <DetailRow label="Academy trust">
              {school.trust ? (
                <Link href={`/trusts/${school.trust.trustId}`} className="text-primary underline underline-offset-2">
                  {school.trust.trustName}
                </Link>
              ) : (
                "Not part of a trust"
              )}
            </DetailRow>
            <DetailRow label="Age range">
              {school.minimumAge !== null && school.maximumAge !== null
                ? `${school.minimumAge} to ${school.maximumAge}`
                : "Not available"}
            </DetailRow>
            <DetailRow label="Gender">{school.gender ?? "Not available"}</DetailRow>
            <DetailRow label="Religious character">{school.religiousCharacter ?? "None"}</DetailRow>
            <DetailRow label="Capacity">{school.capacity ?? "Not available"}</DetailRow>
            <DetailRow label="Number on roll">{school.numberOfPupils ?? "Not available"}</DetailRow>
            <DetailRow label="Opening date">{formatDate(school.openingDate)}</DetailRow>
            <DetailRow label="Website">
              {school.website ? (
                <a href={school.website} className="text-primary underline underline-offset-2" rel="noreferrer">
                  {school.website}
                </a>
              ) : (
                "Not available"
              )}
            </DetailRow>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Published performance metrics</CardTitle>
          </CardHeader>
          <CardContent>
            {latestMetricsByCode.size === 0 ? (
              <p className="text-muted-foreground text-sm">
                No published metrics are available for this school yet.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Metric</TableHead>
                    <TableHead>Value</TableHead>
                    <TableHead>Academic year</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Array.from(latestMetricsByCode.values()).map((metric) => {
                    const definition = getMetricDefinition(metric.metricCode);
                    return (
                      <TableRow key={metric.id}>
                        <TableCell>{definition?.label ?? metric.metricCode}</TableCell>
                        <TableCell>
                          {metric.suppressed
                            ? "Suppressed (small cohort)"
                            : formatMetricValue(metric.valueNumeric, definition)}
                          {metric.provisional && (
                            <Badge variant="outline" className="ml-2">
                              Provisional
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>{metric.academicYear}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
