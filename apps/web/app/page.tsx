import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getPrismaClient } from "@/lib/prisma";
import { safeQuery } from "@/lib/safe-query";
import { formatNumber } from "@/lib/format";

// Revalidate hourly rather than on every request: this figure does not need
// to be second-fresh, and re-querying on every hit would spend free-tier
// database usage for no user-visible benefit.
export const revalidate = 3600;

async function getHomeStats() {
  return safeQuery(
    "home-stats",
    async () => {
      const prisma = getPrismaClient();
      const [schoolCount, trustCount, localAuthorityCount] = await Promise.all([
        prisma.school.count({ where: { status: "OPEN" } }),
        prisma.academyTrust.count(),
        prisma.localAuthority.count(),
      ]);
      return { schoolCount, trustCount, localAuthorityCount };
    },
    { schoolCount: 0, trustCount: 0, localAuthorityCount: 0 },
  );
}

export default async function HomePage() {
  const stats = await getHomeStats();

  return (
    <div className="flex flex-col gap-10">
      <section className="flex flex-col gap-4">
        <h1 className="text-3xl font-semibold tracking-tight">
          Search and compare schools across England
        </h1>
        <p className="text-muted-foreground max-w-2xl">
          SchoolScope England brings together official school records, academy
          trust structures, published performance statistics and admissions
          catchment areas from government sources, in one place.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link href="/schools">Search schools</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/admissions">Check an admissions area</Link>
          </Button>
        </div>
      </section>

      <section
        aria-label="Dataset overview"
        className="grid gap-4 sm:grid-cols-3"
      >
        <Card>
          <CardHeader>
            <CardDescription>Open schools</CardDescription>
            <CardTitle className="text-2xl">
              {stats.ok
                ? formatNumber(stats.data.schoolCount)
                : "Not available"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Academy trusts</CardDescription>
            <CardTitle className="text-2xl">
              {stats.ok ? formatNumber(stats.data.trustCount) : "Not available"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Local authorities</CardDescription>
            <CardTitle className="text-2xl">
              {stats.ok
                ? formatNumber(stats.data.localAuthorityCount)
                : "Not available"}
            </CardTitle>
          </CardHeader>
        </Card>
      </section>

      <section
        aria-label="What you can do here"
        className="grid gap-4 sm:grid-cols-3"
      >
        <Card>
          <CardHeader>
            <CardTitle>Compare schools</CardTitle>
            <CardDescription>
              Filter by phase, local authority, admissions type and published
              performance metrics.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              href="/schools"
              className="text-primary text-sm underline underline-offset-2"
            >
              Browse schools
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Check a catchment area</CardTitle>
            <CardDescription>
              See whether an address falls inside a school&apos;s published
              priority area, where a local authority has made that boundary
              available.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              href="/admissions"
              className="text-primary text-sm underline underline-offset-2"
            >
              Go to admissions
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Explore the map</CardTitle>
            <CardDescription>
              View schools and available catchment boundaries together on an
              interactive map.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              href="/map"
              className="text-primary text-sm underline underline-offset-2"
            >
              Open the map
            </Link>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
