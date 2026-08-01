import type { Metadata } from "next";
import Link from "next/link";
import { getPilotLocalAuthorityCodes } from "@schoolscope/shared";
import { AdmissionsCheckForm } from "@/components/admissions-check-form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getPrismaClient } from "@/lib/prisma";
import { safeQuery } from "@/lib/safe-query";

export const metadata: Metadata = {
  title: "Admissions",
};

// The pilot local authority list changes rarely; revalidate hourly rather
// than baking in whatever the database returned (or didn't) at build time.
export const revalidate = 3600;

async function getPilotAuthorities() {
  const prisma = getPrismaClient();
  const codes = getPilotLocalAuthorityCodes();
  if (codes.length === 0) return [];
  return prisma.localAuthority.findMany({
    where: { code: { in: codes } },
    select: { code: true, name: true },
    orderBy: { name: "asc" },
  });
}

export default async function AdmissionsPage() {
  const pilotAuthorities = await safeQuery("admissions-pilot-authorities", getPilotAuthorities, []);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Check an admissions area</h1>
        <p className="text-muted-foreground mt-1 max-w-2xl text-sm">
          Enter a postcode to see whether it falls inside a published school priority or catchment
          area. This tool only covers local authorities that publish an official, machine-readable
          boundary; everywhere else will honestly show as not available.
        </p>
      </div>

      <Alert variant="warning">
        <AlertTitle>This is not an admissions decision</AlertTitle>
        <AlertDescription>
          A result here shows the published boundary for the selected academic year. It does not
          guarantee that a school place will be offered. Always confirm with the local authority
          or admission authority&apos;s own official checker before applying.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>Check a postcode</CardTitle>
        </CardHeader>
        <CardContent>
          <AdmissionsCheckForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Local authorities currently covered</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          {pilotAuthorities.data.length === 0 ? (
            <p className="text-muted-foreground">No local authorities are configured yet.</p>
          ) : (
            <ul className="list-inside list-disc">
              {pilotAuthorities.data.map((la) => (
                <li key={la.code}>
                  <Link href={`/local-authorities/${la.code}`} className="text-primary underline underline-offset-2">
                    {la.name}
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <p className="text-muted-foreground mt-3">
            See{" "}
            <Link href="/local-authorities" className="underline underline-offset-2">
              all local authorities
            </Link>{" "}
            for coverage status everywhere else.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
