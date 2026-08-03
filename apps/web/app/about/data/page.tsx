import type { Metadata } from "next";
import Link from "next/link";
import { listMetricDefinitions } from "@catchment-zone/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "About the data",
};

export default function AboutDataPage() {
  const metrics = listMetricDefinitions();

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          About the data
        </h1>
        <p className="text-muted-foreground mt-1 max-w-2xl text-sm">
          Every figure on this site traces back to an official, publicly
          documented source. If a source is not listed here, it is not used.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>England: school and trust directory</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p>
            <a
              href="https://get-information-schools.service.gov.uk/"
              className="text-primary underline underline-offset-2"
              rel="noreferrer"
            >
              Get Information about Schools (GIAS)
            </a>
            , the Department for Education&apos;s live register of schools,
            academies, colleges and trusts. School and trust records are
            refreshed from GIAS&apos;s published data extracts.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Scotland: school register</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p>
            The Scottish Government&apos;s ScottishSchoolRoll dataset, published
            as a live map service at{" "}
            <a
              href="https://www.data.gov.scot/"
              className="text-primary underline underline-offset-2"
              rel="noreferrer"
            >
              maps.gov.scot
            </a>
            . Schools are identified by their SEED code / SchUID rather than a
            GIAS-style URN. This source has no open/closed status field, so
            every Scottish school here is treated as currently open.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Wales: school register</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p>
            <a
              href="https://datamap.gov.wales/layers/geonode:maintained_schools_wg"
              className="text-primary underline underline-offset-2"
              rel="noreferrer"
            >
              DataMapWales&apos;s maintained-schools register
            </a>
            , compiled by Welsh Government from OS AddressBase, My Local School
            and its own published address list of schools. Like Scotland&apos;s
            source, it has no open/closed status field, so every Welsh school
            here is treated as currently open.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Published performance statistics</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p>
            Sourced from the{" "}
            <a
              href="https://api.education.gov.uk/statistics/docs/"
              className="text-primary underline underline-offset-2"
              rel="noreferrer"
            >
              Explore Education Statistics API
            </a>
            , including DfE&apos;s official school performance tables: key stage
            2 (SATs) results for primary schools and key stage 4 (GCSE) results,
            including Attainment 8 and Progress 8, for secondary schools.
            Suppressed figures (where a cohort is too small to publish without
            risking identifying individual pupils) are shown as suppressed,
            never estimated or backed out. Where a measure is not applicable or
            not yet published for a school (e.g. Progress 8 in the most recent
            release, or a scaled score for a subject that has none), it is shown
            as not available rather than as zero or suppressed.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Admissions catchment areas</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p>
            There is no single national catchment dataset for Great Britain.
            Coverage is built local authority by local authority, only where a
            verified, licensed, machine-readable boundary source exists, under
            each publisher&apos;s own open licence (Open Government Licence v3.0
            or equivalent). See{" "}
            <Link href="/admissions" className="underline underline-offset-2">
              Check an admissions area
            </Link>{" "}
            for the current list of covered local authorities. Local authorities
            without a listed source show as &ldquo;not available&rdquo;, never a
            guess.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Metric definitions</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2">
            {metrics.map((metric) => (
              <div key={metric.code}>
                <dt className="text-sm font-medium">{metric.label}</dt>
                <dd className="text-muted-foreground text-sm">
                  {metric.description}
                </dd>
                <dd className="text-muted-foreground mt-1 text-xs">
                  {metric.comparability_notes}
                </dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>What we deliberately do not use</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <ul className="list-inside list-disc space-y-1">
            <li>
              Interactive council map applications with no documented API or
              reuse licence.
            </li>
            <li>
              Any source without an explicit, checkable licence statement.
            </li>
            <li>
              A composite or aggregated &ldquo;best school&rdquo; ranking.
            </li>
            <li>
              Northern Ireland&apos;s school register: the only machine-readable
              source found (Open Data NI&apos;s &ldquo;School Locations&rdquo;
              dataset) has been stale since February 2016, with no current
              extract available. Rather than show schools that may no longer be
              accurate, Northern Ireland is not covered here at all.
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
