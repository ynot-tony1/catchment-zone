# Project status

Updated 2026-08-01. Reflects what has actually been run and verified on
disk, not what is intended.

## Completed and verified

- **Monorepo baseline is green.** `pnpm install`, `pnpm -r typecheck`,
  `pnpm -r lint`, `pnpm -r test`, and a real
  `pnpm --filter @schoolscope/web build` (Next.js production build, fake
  local `DATABASE_URL` so Prisma can generate its client) all pass. Test
  counts: `packages/shared` 39, `apps/web` 29, `services/ingestor` 45.
- **Every app route from the original spec now exists and is wired to the
  database** (degrading gracefully via `safeQuery` when unreachable, never
  a 500 page):
  - `/` home dashboard (live counts, ISR hourly).
  - `/schools` search (name/postcode/status filters, keyset pagination,
    distance-from-point sort) and `/schools/[urn]` detail (address, trust,
    local authority, de-duplicated latest-per-metric performance table).
  - `/trusts` and `/trusts/[id]`.
  - `/local-authorities` and `/local-authorities/[code]` (admissions
    links, catchment source list, schools in that authority).
  - `/admissions`: postcode + phase catchment check, calling
    `/api/admissions/check`, rendering the mandatory disclaimer text
    verbatim and, when applicable, the near-boundary warning. The status
    vocabulary and copy were written to only ever use the six allowed
    `CatchmentCheckStatus` values, matching the forbidden-word test
    already in `packages/shared`.
  - `/map`: MapLibre view, schools loaded live for the current viewport
    via `/api/map/schools`; `/api/map/catchments` also exists for
    boundary overlays once catchment data exists.
  - `/about/data`, `/status` (DB connectivity, git SHA, last 10 ingestion
    runs).
  - API routes: `/api/schools`, `/api/trusts`, `/api/local-authorities`,
    `/api/admissions/check` (rate-limited via the existing
    `lib/rate-limit.ts`), `/api/map/schools`, `/api/map/catchments`. All
    Node runtime, all using the shared safe-error-envelope helpers.
- **Query layer** (`apps/web/lib/queries/`): `schools.ts`, `trusts.ts`,
  `local-authorities.ts`, `catchments.ts`. Catchment checking does a
  bounding-box prefilter then exact point-in-polygon via the existing
  `lib/geo.ts` Turf helpers, distinguishes
  `OFFICIAL_BOUNDARY_NOT_AVAILABLE` from `ACADEMIC_YEAR_NOT_AVAILABLE`
  using the existing `packages/shared` catchment-source-registry helpers,
  and flags `POSTCODE_RESULT_NEAR_BOUNDARY` using the configured warning
  distance, matching the spec's admissions-safety rules.
- **Toolchain compatibility fixes** made while establishing the baseline
  (see git history for detail): TypeScript pinned to `~6.0.3` in
  `apps/web`/`packages/shared` (TS 7 not yet supported by
  `typescript-eslint`); `apps/web` ESLint rewritten onto
  `eslint-config-next`'s native flat-config exports and pinned to
  `~9.39.5` (ESLint 10 breaks `eslint-plugin-react`); `next.config.ts`'s
  removed `eslint.dirs` option (Next.js 16 dropped built-in ESLint
  integration); a zod v4 tuple-pipe type error in
  `packages/shared/src/schemas/common.ts`; a Turf `MultiPolygon` handling
  bug in `apps/web/lib/geo.ts`; and a real `.gitignore` bug that left the
  generated Prisma client, including a native binary, untracked but
  unignored (actual `output` path is `packages/database/generated`, not
  `packages/database/prisma/generated`).
- **`services/ingestor/Dockerfile` verified end-to-end**: `docker build`
  succeeds, and `docker run schoolscope-ingestor:local --help` shows the
  expected CLI (`discover-gias`, `import-gias`, `import-trusts`,
  `import-statistics`, `import-catchments`, `import-admissions`,
  `refresh-metrics`, `verify`, `cleanup`, `run`). The local test image was
  removed after verification; nothing was pushed anywhere.
- **`services/ingestor`** full check suite still passes: `ruff check .`,
  `mypy src` (13 files), `pytest -q` (45 tests).

## Unfinished

- **No GitHub repository created or pushed.** Nothing in this project has
  left this machine.
- **No CockroachDB Cloud connection.**
  `scripts/bootstrap-cockroachdb.sh` supports reading
  `COCKROACH_BOOTSTRAP_URL` from a gitignored `.env.cockroach.local` file
  at the repo root as well as a shell variable, but has not been run: it
  needs a GitHub repo (for `gh secret set`) and a linked Vercel project
  (for `vercel env add`) to exist first.
- **No GitHub secrets/variables, no Vercel project link, no migration
  applied to any real database, no data imported, no production
  deployment.**
- **Playwright end-to-end tests do not exist yet** (`playwright.config.ts`
  is present but there is no `tests/e2e/` content). Not attempted this
  session; would need a running app and, for full coverage, real data.
- **`/map`'s catchment overlay is wired but unused**: `/api/map/catchments`
  works, but the map page does not yet render a toggle to show catchment
  polygons on top of school points. Schools-only view is functional.

## Known failing tests

None. Every test suite that was run passed: `packages/shared` (39),
`apps/web` (29), `services/ingestor` (45).

## Exact next steps, in order

1. Commit this work, then `gh repo create` and push.
2. Bootstrap `aqua-roach` via `scripts/bootstrap-cockroachdb.sh` (needs
   step 1 done first), writing scoped credentials to GitHub secrets and
   Vercel.
3. Run the `migrate-production` GitHub Actions workflow manually.
4. `vercel link`, root directory `apps/web`, verify a preview deployment.
5. Run the bounded pilot import, fill in `scripts/calibration-report.md`
   with real numbers, get explicit go-ahead before any larger import.
6. Verify a real production deployment end-to-end against the acceptance
   criteria in the original spec.
7. Optional polish once the above is live: catchment overlay toggle on
   `/map`, Playwright e2e coverage for the golden paths (search a school,
   check a postcode, view the map).
