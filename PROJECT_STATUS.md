# Project status

Snapshot taken 2026-08-01, mid-build, on user request to pause. This file
reflects what was verified on disk at pause time, not what was intended or
in flight. Two background build agents (Python ingestion service, Next.js
web app) were still running when this snapshot was taken; their work up to
this point is included below, anything after this point is not.

## Completed and verified

* **Monorepo scaffold**: `pnpm-workspace.yaml`, root `package.json`,
  `.gitignore`, `.env.example`, `docker-compose.yml`. No secrets committed;
  verified `.env`, `.env.local`, `apps/web/.env.local`,
  `packages/database/.env` are all gitignored and were not staged.
* **Database schema**: `packages/database/prisma/schema.prisma` complete,
  covering every model in the spec (School, AcademyTrust,
  SchoolRelationship, LocalAuthority, SchoolMetric, CatchmentSource,
  CatchmentArea, SchoolCatchmentArea join table, AdmissionArrangement,
  HistoricalOffer, PostcodeCache, IngestionRun). No migration has been
  generated yet (`packages/database/prisma/migrations/` is empty); that
  requires `prisma migrate dev` against a real database, which does not
  exist yet.
* **Source registry config**: `config/catchment-sources.yml`,
  `config/statistics-sources.yml`, `config/metric-definitions.yml`. The
  catchment source (Sheffield City Council, primary and secondary
  boundaries, academic year 2025-2026) was verified against the publisher's
  live ArcGIS item metadata (licence, Feature Service URL) via direct fetch,
  not fabricated. GIAS and DfE Explore Education Statistics API endpoints
  were similarly verified against real documentation.
* **GitHub Actions workflows**: `ci.yml`, `ingest-gias.yml`,
  `ingest-school-statistics.yml`, `ingest-catchments.yml`,
  `migrate-production.yml`, plus `dependabot.yml`, issue templates, and a PR
  template. Not yet run for real (no GitHub remote connected yet), so their
  YAML has not been validated by an actual Actions run.
* **Documentation**: `README.md`, `LICENSE`, and all ten files under
  `docs/` (architecture, admissions-and-catchments, database, data-sources,
  deployment, ingestion, methodology, operations, privacy, troubleshooting),
  plus `scripts/bootstrap-cockroachdb.sh` and
  `scripts/calibration-report.md` (report template, not yet populated with
  real numbers).
* **Python ingestion service** (`services/ingestor/`): CLI (`cli.py`),
  config, structured logging, db helpers, pydantic models, geometry
  utilities, pipeline orchestration, and four adapters (GIAS, statistics,
  catchments, admissions) are written. Verified by actually running the
  tools in this session:
  * `ruff check .` -> all checks passed
  * `mypy src` -> no issues found in 13 source files
  * `pytest -q` -> **45 passed**, 0 failed
  * These tests run against invented fixtures
    (`tests/fixtures/gias_sample.csv`, `tests/fixtures/sheffield_catchment_sample.geojson`)
    and mocked database access; nothing here has been exercised against a
    real GIAS download, a real EES API response, or a live database.

## Unfinished

* **`services/ingestor/Dockerfile` does not exist yet.** The service cannot
  currently be containerized or run via
  `docker compose --profile ingestion`. This blocks the "Docker build" CI
  job and any container-based deployment of the ingestor.
* **Next.js web app (`apps/web/`) is scaffolding only, not a working app.**
  Present: package/tool config (`package.json`, `tsconfig.json`,
  `next.config.ts`, ESLint, Vitest, Playwright configs), shadcn-style UI
  primitives under `components/ui/`, and library helpers (`lib/env.ts`,
  `lib/logger.ts`, `lib/prisma.ts`, `lib/api-response.ts`,
  `lib/safe-query.ts`, `lib/utils.ts`). **Missing**: `app/layout.tsx`,
  `app/page.tsx`, every route under section 7 of the spec (`/schools`,
  `/schools/[urn]`, `/admissions`, `/map`, `/trusts`, `/local-authorities`,
  `/about/data`, `/status`), and every API route under `app/api/`. Only
  `app/globals.css` exists under `app/`. **`pnpm install` has not been run**
  (no `node_modules` anywhere in the workspace), so nothing has been built,
  linted, typechecked, or tested for this package. Any claim that the web
  app "builds" or "passes tests" would be false at this snapshot.
* **`packages/shared`** has Zod schemas (`school.ts`, `catchment.ts`,
  `common.ts`, `trust.ts`, `map.ts`), constants, and a config-sync script
  (`scripts/sync-config.mjs`, presumably meant to turn the YAML files in
  `config/` into `packages/shared/src/generated/` at install time, per the
  `.gitignore` entry added for that path) with several `*.test.ts` files
  present. None of these tests have been run yet (same `pnpm install`
  blocker as above).
* **No GitHub repository created or pushed.** `git status` shows "No
  commits yet" until this session's commit. `gh repo create` has not been
  run.
* **No CockroachDB Cloud connection.** The `aqua-roach` cluster has not
  been bootstrapped. `scripts/bootstrap-cockroachdb.sh` exists but has never
  been executed; `COCKROACH_BOOTSTRAP_URL` has not been provided.
* **No GitHub secrets or variables configured** (`INGEST_DATABASE_URL`,
  `MIGRATION_DATABASE_URL`, `INGESTION_ENABLED`,
  `CATCHMENT_INGESTION_ENABLED`). Blocked on the CockroachDB bootstrap
  above.
* **No Vercel project linked.** `vercel link` has not been run against this
  directory; no environment variables have been set on Vercel.
* **No migration has ever been applied to any real database**, local or
  cloud.
* **No data has been imported.** The free-tier calibration report
  (`scripts/calibration-report.md`) is an unfilled template.
* **No production deployment exists.** There is no live URL.

## Known failing tests

None. Every test suite that was actually run (`services/ingestor`, 45
tests) passed. The web app and `packages/shared` test suites have not been
run at all (blocked on `pnpm install`), so "no failures" there means
"unverified," not "passing."

## Exact next steps, in order

1. Run `pnpm install` at the repo root, then `pnpm --filter @schoolscope/database generate`, `pnpm typecheck`, `pnpm lint`, `pnpm test` to get a real baseline for `apps/web` and `packages/shared`. Expect failures given `app/layout.tsx` etc. do not exist yet; that is the actual next build task, not a regression.
2. Finish `apps/web/app/`: root layout, home dashboard, and the remaining seven routes plus API routes listed above.
3. Write `services/ingestor/Dockerfile` and verify `docker build`.
4. Once both `apps/web` and `services/ingestor` build/lint/typecheck/test cleanly, commit that work, then run `gh repo create` and push.
5. You export `COCKROACH_BOOTSTRAP_URL` for the `aqua-roach` cluster in your own shell (never in chat) and run `scripts/bootstrap-cockroachdb.sh`; this writes `MIGRATION_DATABASE_URL` / `INGEST_DATABASE_URL` to GitHub secrets and `DATABASE_URL` to Vercel directly, then you unset the bootstrap variable.
6. Run the `migrate-production` GitHub Actions workflow manually to apply the first migration to `school_intelligence`.
7. `vercel link`, set root directory to `apps/web`, connect the GitHub integration, verify a preview deployment.
8. Run the bounded pilot import (10,000 schools, trusts, selected metrics, Sheffield catchments), fill in `scripts/calibration-report.md` with real before/after numbers, and get your explicit go-ahead before any larger import.
9. Verify a real production deployment end-to-end against the acceptance criteria checklist in the original spec.

## What was committed in this pause

Everything currently on disk except gitignored files (`node_modules`,
`.venv`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.env`
and `.env.local` variants, Prisma generated client output). This is the
first commit on `main`; nothing has been pushed to any remote.
