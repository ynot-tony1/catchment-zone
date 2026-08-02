import type { Metadata } from "next";
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
          <CardTitle>School and trust directory</CardTitle>
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
            refreshed from GIAS&apos;s published data extracts. GIAS covers
            England only; Scotland, Wales and Northern Ireland each have their
            own official school register and are added here as separate sources,
            nation by nation, not assumed to share GIAS&apos;s identifiers or
            update schedule.
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
            . Suppressed figures (where a cohort is too small to publish without
            risking identifying individual pupils) are shown as suppressed,
            never estimated or backed out.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Admissions catchment areas</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <p>
            There is no single national catchment dataset for England. Coverage
            is built local authority by local authority, only where a verified,
            licensed, machine-readable boundary source exists. The current pilot
            source is Sheffield City Council&apos;s published Primary and
            Secondary Catchment Boundaries, under the Open Government Licence
            v3.0. Local authorities without a listed source show as &ldquo;not
            available&rdquo;, never a guess.
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
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
