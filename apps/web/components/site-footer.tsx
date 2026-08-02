import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-border mt-16 border-t">
      <div className="text-muted-foreground mx-auto max-w-6xl px-4 py-8 text-sm">
        <p>
          Contains public sector information from the Department for Education,
          licensed under the{" "}
          <a
            href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
            className="underline underline-offset-2"
            rel="noreferrer"
          >
            Open Government Licence v3.0
          </a>
          . See{" "}
          <Link href="/about/data" className="underline underline-offset-2">
            About the data
          </Link>{" "}
          for source details and update frequency.
        </p>
        <p className="mt-2">
          catchment-zone is an independent project, not affiliated with the
          Department for Education, the devolved education departments of
          Scotland or Wales, or any local authority.
        </p>
      </div>
    </footer>
  );
}
