# Project status

Updated 2026-08-01. Reflects what has actually been run and verified on
disk, not what is intended.

## Completed and verified

* **Monorepo baseline is green.** `pnpm install`, `pnpm -r typecheck`,
  `pnpm -r lint`, and `pnpm -r test` all pass across every workspace
  package (`packages/shared`: 39 tests, `apps/web`: 25 tests). A real
  `pnpm --filter @schoolscope/web build` (Next.js production build, with a
  fake local `DATABASE_URL` so Prisma can generate its client) also
  succeeds.
* **Toolchain compatibility fixes** made while establishing that baseline:
  * `typescript` pinned to `~6.0.3` in `apps/web` and `packages/shared`
    (the default `^7.0.2` resolved to the new TS 7 compiler, which
    `typescript-eslint` 8.65.0 does not support yet).
  * `apps/web`'s ESLint config rewritten to use `eslint-config-next`'s
    native flat-config exports (`eslint-config-next/core-web-vitals`,
    `eslint-config-next/typescript`) instead of the legacy `FlatCompat`
    bridge, which crashed under ESLint 10 with a circular-JSON error.
  * `apps/web`'s `eslint` pinned to `~9.39.5`: `eslint-plugin-react`
    7.37.5 (pulled in by `eslint-config-next`) calls a `context.getFilename`
    API that ESLint 10 removed, crashing on any component file.
  * `next.config.ts`'s `eslint.dirs` option removed: Next.js 16 dropped
    the built-in ESLint integration entirely, so that key no longer exists
    on `NextConfig`.
  * `packages/shared/src/schemas/common.ts`'s `BboxQuerySchema` fixed: the
    `.transform().pipe()` chain did not typecheck against zod v4's tuple
    input type; the transform now casts to the tuple's own declared input
    shape.
  * `apps/web/lib/geo.ts`'s `distanceToBoundaryMetres` fixed: it only
    handled a `LineString` result from `polygonToLine`, but a
    `MultiPolygon` produces `MultiLineString`, which
    `pointToLineDistance` cannot take directly; now normalised via
    `@turf/flatten` first.
  * **A real `.gitignore` bug found and fixed**: it excluded
    `packages/database/prisma/generated/`, but the schema's actual
    `output` path (`packages/database/prisma/schema.prisma`, `output =
    "../generated"`) resolves to `packages/database/generated`, one level
    up. The compiled Prisma client, including a native query-engine binary,
    was untracked-but-unignored until this was corrected.
* **Next.js app now has real pages**, not just scaffolding:
  * `app/layout.tsx`, `app/page.tsx` (home dashboard with live open
    school / trust / local authority counts, ISR-revalidated hourly).
  * `app/schools/page.tsx`: search form (name, postcode, status) plus a
    results table, backed by `lib/queries/schools.ts`, which supports
    filtering, keyset (not offset) pagination via the existing
    `encodeCursor`/`decodeCursor` helpers, and a distance-from-point sort
    (bounding-box prefilter, then exact great-circle sort/filter in
    memory, since there is no PostGIS).
  * `app/schools/[urn]/page.tsx`: school detail, address, local authority
    and trust links, and a de-duplicated latest-value-per-metric-code
    table with suppressed/provisional labelling.
  * `app/api/schools/route.ts`: JSON GET endpoint over the same query
    function, Node runtime, safe error envelope, cache headers.
  * `app/about/data/page.tsx`: static sourcing and metric-definition copy,
    no fabricated sources, matches `docs/data-sources.md`.
  * `app/status/page.tsx`: live database connectivity check, deployed git
    SHA, and the 10 most recent `IngestionRun` rows.
  * New unit tests: `lib/geo.test.ts`, `lib/format.test.ts` (25 tests,
    listed above).
* **`services/ingestor/Dockerfile`** now exists (multi-stage, non-root
  runtime user, config mounted at container-run time since it lives
  outside the Docker build context). Not yet verified with a real `docker
  build` in this session (Docker was not invoked here).
* **`services/ingestor` adapters/statistics.py** was reworked (by the
  background agent, verified by re-running the full check suite in this
  session): `ruff check .` passes, `mypy src` passes (13 files), `pytest
  -q` passes (45 tests). It now resolves EES publication IDs via the
  search endpoint rather than assuming a slug works directly as an id, and
  leaves an explicit, documented TODO in `fetch_dataset_rows` about
  mapping opaque indicator/filter IDs to this repo's metric codes, which
  needs confirming against a real dataset response before
  `import_statistics` can persist rows.

## Unfinished

* **Still missing app routes**: `/admissions` (catchment/postcode check,
  with the mandatory disclaimer and near-boundary text), `/map`
  (MapLibre view), `/trusts` and `/trusts/[id]`, `/local-authorities` and
  `/local-authorities/[code]`, and their supporting API routes
  (`/api/admissions/check`, `/api/map/schools` or similar, `/api/trusts`,
  `/api/local-authorities`).
* **No GitHub repository created or pushed.**
* **No CockroachDB Cloud connection.** `scripts/bootstrap-cockroachdb.sh`
  now supports reading `COCKROACH_BOOTSTRAP_URL` from a gitignored
  `.env.cockroach.local` file at the repo root as well as a shell
  variable, but it has not been run: it still needs a GitHub repo (for
  `gh secret set`) and a linked Vercel project (for `vercel env add`) to
  exist first.
* **No GitHub secrets/variables, no Vercel project link, no migration
  applied to any real database, no data imported, no production
  deployment.** Same as before, unchanged.
* **`docker build` for `services/ingestor` has not been run** in this
  session; the Dockerfile exists but is unverified end-to-end.

## Known failing tests

None. Every test suite that was run passed: `packages/shared` (39),
`apps/web` (25), `services/ingestor` (45).

## Exact next steps, in order

1. Build the remaining four route groups (`/admissions`, `/map`,
   `/trusts`, `/local-authorities`) and their API routes, with tests, the
   same way the schools routes were done.
2. Verify `docker build` for `services/ingestor`.
3. Commit that work, then `gh repo create` and push.
4. Bootstrap `aqua-roach` via `scripts/bootstrap-cockroachdb.sh` (needs
   step 3 done first), writing scoped credentials to GitHub secrets and
   Vercel.
5. Run the `migrate-production` GitHub Actions workflow manually.
6. `vercel link`, root directory `apps/web`, verify a preview deployment.
7. Run the bounded pilot import, fill in `scripts/calibration-report.md`
   with real numbers, get explicit go-ahead before any larger import.
8. Verify a real production deployment end-to-end.
