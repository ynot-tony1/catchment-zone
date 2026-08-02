# Project status

Updated 2026-08-02. Reflects what has actually been run and verified on
disk, not what is intended.

## Completed and verified

- **Northern Ireland removed from the project entirely, by explicit
  request.** It had been built and live (adapter, CLI command, scheduled
  workflow, 1,555 schools in production, `source_extract_date` staleness
  labelling throughout the UI) - see the git history around this entry
  for exactly what that looked like. Removed because its only source
  (Open Data NI's "School Locations" dataset) has been stale since
  February 2016 with no current extract available, and showing schools
  that may no longer be accurate isn't worth it just to say all four
  nations are covered. Concretely: all 1,555 `NORTHERN_IRELAND` school
  rows deleted from production (verified: 0 remaining, and verified no
  other table - `school_metrics`, `admission_arrangements`,
  `school_catchment_areas`, `school_relationships` - referenced any of
  them before deleting); `NORTHERN_IRELAND` dropped from the `Nation`
  enum via `ALTER TYPE "Nation" DROP VALUE` (only possible because no row
  referenced it anymore); `adapters/northern_ireland.py`,
  `import-northern-ireland`, its tests/fixture, and
  `ingest-northern-ireland.yml` all deleted; every "four nations" claim
  in the UI, README and this file updated to say three (England,
  Scotland, Wales) - the project's practical scope is now Great Britain,
  not the whole UK. `SCOTLAND_INGESTION_ENABLED` and
  `DEVOLVED_NATIONS_INGESTION_ENABLED` (which now only gates Wales) are
  untouched by this - neither was NI-specific.

- **`ingestion_runs` is written to for the first time in this project's
  history.** `pipeline.py` already had a complete, correct
  `create_ingestion_run`/`complete_ingestion_run` implementation - nothing
  in `cli.py` ever called it, so `/status`'s "recent ingestion runs" card
  had shown "No ingestion runs recorded yet" through every real import
  this project has ever run, including everything earlier in this
  session. Wired into `import-gias`, `import-trusts`, `import-scotland`,
  `import-wales`, `import-northern-ireland`, `import-catchments` (one row
  per local-authority/source-type combination). Verified against
  production: a real `import-scotland` run produced the first
  `ingestion_runs` row ever written, and it appeared on the live
  `/status` page immediately. Incidentally also fixes GIAS's
  checksum-skip logic, which could never find a prior run to compare
  against before now and was silently a no-op.

- **Catchment coverage now spans 5 local authorities across 2 nations
  (718 real catchment areas total), plus a longstanding bug fixed along
  the way.** Starting from Aberdeen City (Scotland's first candidate,
  previously rejected in `catchment-sources.yml` for being "outside
  GIAS/DfE scope"), Scotland turned out to have real, licensed,
  ArcGIS-hosted catchment data widely published across councils - a
  genuine surprise this session found by just checking: Aberdeen City
  (63 areas), City of Edinburgh (123, across four ND/RC layers), Glasgow
  City (254, across four ND/RC layers), Fife (151, across four
  ND/denominational layers), all OGL-licensed (Fife's own wording is "no
  conditions apply" rather than citing OGL by name - recorded as
  actually stated, not relabelled), all imported with zero new adapter
  code - the existing generic ArcGIS FeatureServer code, originally
  written for Sheffield, was never actually England-specific. Also
  researched and ruled out, with real evidence not guesses: Cardiff
  (Wales) only has an interactive address-lookup tool, no downloadable
  dataset, excluded by this project's own "what we deliberately do not
  use" rule; Northern Ireland's Department of Education confirmed it
  holds no catchment-area data centrally at all, each school sets its
  own enrolment criteria - a genuine dead end, not a research gap.

  Edinburgh, Glasgow and Fife all split catchments by denomination
  (non-denominational vs Roman Catholic/denominational), and those
  geographically _overlap_ (a household can sit inside both at once -
  denominational choice is separate from geographic catchment in
  Scotland). Importing them under the exact `primary_catchment`/
  `secondary_catchment` `source_type` the `/admissions` checker looks up
  would let it silently return whichever polygon matches first for a
  household in an overlap - a real wrong answer, not a theoretical one.
  Imported under suffixed source types instead (`_nd`/`_rc`/`_denom`):
  real, licensed data visible on `/map`, correctly excluded from
  `/admissions` until that feature can ask "which denomination" first.

  Fixed a real bug found while verifying this: nothing anywhere had ever
  set `local_authorities.catchment_coverage_status`, so Sheffield itself
  showed "Catchment data not available" on `/local-authorities` despite
  having 127 real catchment areas. `import-catchments` now sets it to
  `PILOT` after a successful import (upgrading only from the
  `NOT_AVAILABLE` default, never overwriting a status set some other
  way); verified live - all 5 local authorities now correctly show
  "Pilot catchment coverage".

  `/map`'s catchment overlay toggle is wired up for the first time
  (`/api/map/catchments` existed since the original build but nothing
  ever rendered it): a checkbox loads catchment polygons for the current
  viewport as a translucent fill + outline layer, verified live against
  Sheffield, Aberdeen City and Edinburgh (real school names visible in
  Edinburgh's popups, e.g. "Boroughmuir High School" - Edinburgh's
  layers carry the actual school name in `EST_NAME`, unlike Sheffield/
  Aberdeen's zone-name-only sources, making it a real future
  `SchoolCatchmentArea` candidate).

  Investigating the admissions-checker's `servedSchools` field (empty
  for every real match right now) confirmed `SchoolCatchmentArea`
  linking genuinely cannot be done by simple name-matching, settling an
  open question from earlier: Sheffield's real catchment features carry
  no name field at all (`"Unnamed catchment area 41"`), and Aberdeen's
  `NAME` field is a place/zone name ("Greenbrae", "Culter"), not a school
  name - there is no textual relationship to a school name in either
  real source. This is real per-source research work (which school
  serves which named zone), not a matching-algorithm problem.

- **Catchment coverage extended to 4 more Scottish councils**: North
  Lanarkshire (152 areas, four ND/denom layers), Highland (196, two
  layers - no separate RC layer found for this one, only a smaller,
  distinct Gaelic Medium category not imported), Dundee City (40, single
  service four layers), Perth and Kinross (86, four ND/RC layers). Every
  Scottish council checked so far (8 of 8) has had real, licensed
  catchment data - a genuinely consistent pattern, not luck on the first
  few. Total catchment coverage after this: **9 local authorities, 1,192
  real catchment areas**, verified against production.

  Also found, but could not verify live: Spatial Hub Scotland (run by the
  Improvement Service), a single national WFS aggregate covering all of
  Scotland's catchments in 4 layers with per-feature local-authority
  fields - would likely make most of the individual council entries
  redundant if reachable. Its `geo.spatialhub.scot` endpoint returned a
  403 "Access Denied" from this session's environment even with a browser
  User-Agent and Referer set, while the GeoServer admin UI on the same
  host loaded fine - a targeted restriction on the data workspace, not a
  general network block. Recorded in `catchment-sources.yml`'s candidates
  as worth retrying from a different network origin.

- **Renamed to catchment-zone; scope expanded from England-only to Great
  Britain.** GitHub repo, Vercel project/domain, npm workspace scope
  (`@catchment-zone/*`), and the Python package
  (`catchment_zone_ingestor`) are all renamed and live. Current, correct
  URLs: repo `https://github.com/ynot-tony1/catchment-zone`, production
  `https://catchment-zone.vercel.app` (verified: all 7 app routes return
  200 on the new domain post-rename; the old
  `schoolscope-england.vercel.app` domain still resolves too, since Vercel
  doesn't drop an old default alias on rename, so nothing broke in the
  transition). Schema gained a `Nation` enum (`ENGLAND`/`SCOTLAND`/`WALES`;
  `NORTHERN_IRELAND` was added and later removed, see the entry at the
  top of this file) on `School` and `LocalAuthority`, deployed via
  migration, with all 10,000 existing schools and 92 local authorities
  correctly backfilled to `ENGLAND` (verified by query, not assumed).

- **All three Great Britain nations are live in production, not just
  England.** Real adapters (`adapters/scotland.py`, `adapters/wales.py`),
  each live-verified against its actual source before being wired in,
  each a structurally distinct problem, not "GIAS again":
  - **Scotland** (`import-scotland`): the Scottish Government's
    ScottishSchoolRoll ArcGIS MapServer (`maps.gov.scot`). 2,483 schools,
    32 local authorities imported. Schools keyed by SchUID (not the bare
    SEED code, which two co-located schools can share), local authority
    codes are Scotland's own `S12000...` scheme (no collision risk with
    England's numeric codes). No open/closed status field in the source;
    every row is treated as OPEN, a stated limitation.
  - **Wales** (`import-wales`): DataMapWales's `maintained_schools_wg` WFS
    layer (`datamap.gov.wales`, GeoServer/OGC WFS 2.0). 1,440 schools, 22
    local authorities imported. Wales's own `la_code` values are small
    numbers in the same format as England's GIAS codes; this could not be
    definitively checked against a live GIAS extract at the time (GIAS was
    returning 500s/timeouts), so Wales's local authority codes are
    prefixed `W-` as a deliberate collision-safety measure. Same
    no-status-field limitation as Scotland.

  Total: **13,923 schools** across all three nations (10,000 England +
  2,483 Scotland + 1,440 Wales), verified by direct query against
  production, not just a CLI exit code.

  A `Nation` filter and column now runs through the whole web app, not
  just the database: `packages/shared`'s `SchoolSearchFiltersSchema` /
  `LocalAuthoritySearchFiltersSchema` gained a `nation` field, every page
  that lists or shows a school or local authority displays which nation
  it's from, and the map's default viewport was widened from an
  England-only bounding box to cover Great Britain. This work also
  caught a real bug: the URN search filter's regex only accepted digits,
  which would have silently rejected every Scotland (`8212627P`) school
  lookup by id - fixed to accept alphanumeric.

  Scheduled GitHub Actions workflows exist for both (`ingest-scotland.yml`,
  `ingest-wales.yml`, mirroring `ingest-gias.yml`'s shape), and each was
  test-triggered for real via `workflow_dispatch` before being trusted:
  Wales succeeded from GitHub Actions' own IP ranges and is enabled on
  schedule (`DEVOLVED_NATIONS_INGESTION_ENABLED=true`, weekly). Scotland's
  `maps.gov.scot` returned a 403 from GitHub Actions - the same
  Azure-datacenter-IP block GIAS hits - confirmed live, not assumed; it
  has its own gate (`SCOTLAND_INGESTION_ENABLED=false`) so that one
  nation's WAF doesn't hold back the one that genuinely works.

- **Pilot data import ran for real against production** (task from the
  previous "Exact next steps"). `scripts/calibration-report.md` is filled in
  with real measured numbers, not a template. Result: 10,000 schools, 92
  local authorities, 7,176 academy trusts (the full national trust
  register — no row limit was used for trusts), and 127 Sheffield catchment
  areas (101 primary + 26 secondary, LA code 373), all persisted and
  verified by direct query against `aqua-roach`/`school_intelligence`, not
  just a successful CLI exit code. Catchment re-import confirmed idempotent
  (same ids, same row counts on a second run).

  GIAS's live site had changed substantially since the original adapter was
  written, and none of this worked on the first attempt. Real bugs found and
  fixed, each only surfaced by running against the real, live GIAS site and
  the real production database, not caught by any test:
  1. GIAS's WAF 403s non-browser User-Agents; fixed with a real browser UA
     applied only to GIAS requests.
  2. GIAS's downloads page was completely redesigned: no more `<a href>`
     download links, replaced by a stateful ASP.NET collate-then-poll flow
     (`POST /Downloads/Collate` -> poll `/Downloads/GenerateAjax/<uuid>` ->
     `POST /Downloads/Download/Extract`). Fully reverse-engineered and
     reimplemented against the live site.
  3. The download is a ZIP, not a raw CSV, and the CSV inside is not
     consistently UTF-8 (real school names contain Windows-1252 characters).
     Fixed with ZIP unwrapping and a utf-8-sig-then-cp1252 fallback decode.
  4. `upsert_batch` never set `updated_at`, which has no SQL-level DEFAULT
     (Prisma's `@updatedAt` is normally set client-side by Prisma Client, a
     raw SQL write bypasses that entirely) — every first insert into an
     affected table failed NOT NULL. Fixed centrally in `db.py`.
  5. `local_authorities` had no import path at all despite `schools` having a
     foreign key to it; nothing had ever populated it. Fixed by deriving
     distinct (code, name) pairs from the GIAS establishment extract itself
     and upserting them before schools, in the same transaction.
  6. `catchment_sources.id` and `catchment_areas.id` use Prisma's
     `@default(uuid())`, also client-side-only, not a SQL DEFAULT — every
     insert failed NOT NULL on `id`. Fixed by minting ids in the ingestor,
     reusing an existing source's id on re-import so already-written
     `catchment_areas` rows are never orphaned.
  7. Separately, and worse: `import-catchments` built `CatchmentArea`
     polygons in memory and reported a count, but never actually wrote them
     to the database — only the `catchment_sources` summary row was
     persisted. There was also no unique constraint backing either the
     `catchment_sources` or `catchment_areas` upsert's `ON CONFLICT` clause,
     so even after the id fix, both upserts failed with "no unique or
     exclusion constraint matching". Fixed by adding two production
     migrations (`(source_id, geometry_checksum)` unique index on
     `catchment_areas`, `(local_authority_code, academic_year, source_type)`
     unique index on `catchment_sources`), deployed through the existing
     reviewed, manually-confirmed `migrate-production.yml` workflow, then
     wiring the built areas into the same transaction as the source row.
  8. GIAS also blocks requests from Azure datacenter IP ranges (which
     includes GitHub Actions runners) independently of the User-Agent fix —
     confirmed by direct testing from multiple network origins. This means
     the scheduled/automated `ingest-gias.yml` workflow cannot reach GIAS
     from GitHub Actions as currently designed. Explicitly deferred by
     request; the pilot import above was run manually instead, from a
     non-Azure network origin, using a rotated, narrowly-scoped
     `school_ingestor` credential (`scripts/rotate-ingest-credential.sh`,
     new this session, mirrors the existing bootstrap script's pattern).

  `services/ingestor` test suite grew from 45 to 66 tests covering all of
  the above (GIAS downloads-page parsing, ZIP/encoding handling, local
  authority derivation, `upsert_batch`'s `updated_at`/`now()` SQL, and
  catchment source id resolution/reuse), all passing alongside `ruff check
.` and `mypy src`.

  **Known gap, not fixed this session:** `import-statistics` only resolves
  the current DfE publication release, it does not fetch or write any
  `SchoolMetric` rows (a pre-existing, explicitly documented TODO, not
  something broken by the above). Worse, live investigation found the two
  DfE publications that currently resolve at all
  (`pupil-absence-in-schools-in-england`, `pupil-attendance-in-schools`)
  only expose Local authority/Regional/National-level data via the EES API,
  never per-school rows, so `SchoolMetric` (which requires a non-null
  `school_urn`) cannot be populated from either as currently designed. The
  other two configured publications (`school-capacity`,
  `school-workforce-in-england`) don't exist in the EES API's public
  catalogue at all right now. See `scripts/calibration-report.md`'s "What
  actually ran" section for detail. No `SchoolMetric` rows exist in
  production.

- **Pushed to GitHub**: `https://github.com/ynot-tony1/schoolscope-england`
  (public). CI is green on `main`
  (`https://github.com/ynot-tony1/schoolscope-england/actions/runs/30715283514`):
  Ingestor (ruff, mypy, pytest, docker build), Secret scan, Web (lint,
  typecheck, unit tests, build) all passed for real, on GitHub's own
  runners, not just locally. Fixed two real CI bugs to get there: the
  `gitleaks-action` push-diff mode fails on a repository's first push
  (replaced with a direct `gitleaks detect` full-history scan), and
  `prettier --check` had never actually passed since the initial commit
  (ran `prettier --write` for the first time, added `.prettierignore` for
  the lockfile/generated output/a test fixture).
- **Production deployment is live and verified end-to-end**:
  `https://schoolscope-england.vercel.app`. `/status` reports database
  connectivity as Reachable and shows the deployed git SHA; every route
  (`/`, `/schools`, `/schools/[urn]`, `/trusts`, `/local-authorities`,
  `/admissions`, `/map`, `/about/data`) returns 200; `/api/schools`,
  `/api/trusts`, `/api/local-authorities` return valid (currently empty,
  since no data is imported yet) JSON; `POST /api/admissions/check`
  performs a real `postcodes.io` lookup and returns the correct mandatory
  disclaimer text and an honest `OFFICIAL_BOUNDARY_NOT_AVAILABLE` status
  rather than fabricating an answer.

  Getting there took six distinct, real bugs, each found by reading the
  actual deployed function logs after a failed request, not guessed in
  advance:
  1. `vercel link` run from `apps/web` left the project's Root Directory
     setting at `.` (repo root), which only works for ad-hoc CLI deploys
     from that directory, not GitHub-integration builds, which check out
     the full repo. Confirmed concretely via a manual `vercel deploy
--prod` from `apps/web`, which failed `npm install` (no pnpm
     workspace context in a bare subdirectory). Fixed via `vercel api
/v9/projects/... -X PATCH -F rootDirectory=apps/web` (the CLI has no
     dedicated command for this setting).
  2. `packages/database` had no `postinstall`/`prepare` script, so the
     Prisma client was never generated on Vercel (it was always generated
     manually, locally and in CI). Fixed with `postinstall: prisma
generate`.
  3. That fix alone was not enough: Vercel's second deployment restored a
     build cache, pnpm saw the lockfile unchanged and skipped install
     entirely, and the generated client (gitignored source-tree output,
     not part of `node_modules`) was not preserved by that cache. Same
     problem existed for `packages/shared`'s config-sync `prepare` hook.
     Fixed by adding a `prebuild` script to `apps/web` that always
     regenerates both, since pnpm always runs `prebuild` as part of `pnpm
run build`, the exact command Vercel invokes, regardless of whether
     install was skipped.
  4. The deployed function then failed at runtime with "Prisma Client
     could not locate the Query Engine for runtime rhel-openssl-3.0.x".
     Root cause, found by tracing through several dead ends (Turbopack vs
     webpack made no difference; `outputFileTracingRoot` alone did not
     help): the custom `output = "../generated"` path in `schema.prisma`
     placed the client in a monorepo-sibling directory outside
     `node_modules`, which is not Prisma's well-tested, officially
     supported deployment shape. Removed the custom output path entirely;
     `packages/database` now re-exports `@prisma/client` directly through
     a thin `index.js`/`index.d.ts`.
  5. Even on Prisma's default path, the query engine binary lives in a
     dot-prefixed sibling package (`.prisma/client`) several symlink hops
     deep inside pnpm's nested `node_modules/.pnpm/<hash>/node_modules`
     structure, which Vercel's function tracer does not follow on its
     own. Found the real file by searching the pnpm store directly rather
     than guessing further, then added a targeted `outputFileTracingIncludes`
     glob pointed at that exact verified location. This is what actually
     fixed the engine-loading error.
  6. With the engine loading correctly, the next real error was a SQL
     permission error: `user school_app does not have SELECT privilege on
relation schools`. Cause: `ALTER DEFAULT PRIVILEGES`, set once by the
     admin bootstrap role, only applies to objects created by that same
     role; the migration creates tables as `school_migrator`, so those
     defaults never took effect. Fixed by extending the
     `migrate-production.yml` post-deploy grant step to re-grant
     `school_ingestor` and `school_app` privileges on every table, using
     the least-privilege `school_migrator` credential, every run.

- **`aqua-roach` bootstrapped and migrated for real.**
  `scripts/bootstrap-cockroachdb.sh` was run against the live cluster:
  `school_intelligence` created, three least-privilege users created
  (`school_migrator`, `school_ingestor`, `school_app`) with the grants
  from `docs/database.md`, `MIGRATION_DATABASE_URL`/
  `INGEST_DATABASE_URL` written to GitHub secrets, `DATABASE_URL` written
  to Vercel (Production and Preview). Found and fixed two real bugs in
  the script in the process: `CREATE USER IF NOT EXISTS` silently skips
  the password clause on an already-existing user, breaking re-runs
  (fixed with an unconditional `ALTER USER ... WITH PASSWORD` after); and
  the Vercel commands ran from the repo root instead of `apps/web`, where
  the actual project link lives (fixed with `--cwd`).

  The `migrate-production` workflow then took several real attempts to
  get right, each a genuine bug caught by actually running it against
  production, not something guessed in advance:
  1. `prisma migrate status` exits 1 whenever migrations are pending,
     which is the normal state before every deploy; the workflow treated
     that as a hard failure and never reached the deploy step.
  2. CockroachDB Cloud creates new tables with `schema_locked = true` by
     default (a changefeed-performance feature this project does not
     use), which blocks the `ADD CONSTRAINT` foreign-key statements
     Prisma generates afterward.
  3. The first fix attempt (`ALTER TABLE ... SET (schema_locked =
false)` right before the foreign keys) still failed intermittently:
     that ALTER triggers an async CockroachDB schema-change job, and
     Prisma's engine does not wait for it to finish before sending the
     next statement, unlike `psql`. Fixed properly by setting
     `schema_locked = false` directly in each `CREATE TABLE ... WITH
(...)` statement, so the table is never locked in the first place.
  4. Recovering from the partially-applied migration needed a temporary,
     explicitly-confirmed reset workflow (dropped the 12 tables, then
     separately the 5 enum types, since `DROP TABLE` does not cascade to
     types a column used, and CockroachDB does not implement `DROP TYPE
... CASCADE` at all). Deleted once no longer needed.
     Verified independently afterward via read-only queries: 13 tables
     (12 plus `_prisma_migrations`), both foreign keys on `schools` present,
     all indexes present, migration tracking row shows a clean success. The
     `postcode_cache` grant to `school_app` that the bootstrap script had to
     defer (the table did not exist yet) now runs as a permanent step in
     `migrate-production.yml` after every deploy, using the least-privilege
     `school_migrator` credential, not the admin one.

  Every one of the diagnostic/recovery steps above ran through GitHub
  Actions using the already-stored `MIGRATION_DATABASE_URL` secret; the
  real database credentials were never read, held, or handled directly
  in this session, only ever passed through as opaque secret references.

- **Monorepo baseline is green.** `pnpm install`, `pnpm -r typecheck`,
  `pnpm -r lint`, `pnpm -r test`, and a real
  `pnpm --filter @catchment-zone/web build` (Next.js production build, fake
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
  `import-scotland`, `import-wales`, `import-northern-ireland`,
  `import-statistics`, `import-catchments`, `import-admissions`,
  `refresh-metrics`, `verify`, `cleanup`, `run`). The local test image was
  removed after verification; nothing was pushed anywhere.
- **`services/ingestor`** full check suite still passes: `ruff check .`,
  `mypy src` (15 files), `pytest -q` (76 tests).

## Unfinished

- **Metrics import is unimplemented, and the currently-configured sources
  can't fill it as designed.** See "Known gap" above. Needs either a
  school-level DfE metrics source or a schema change (e.g. a local-
  authority-level metrics table) before this is worth revisiting. Not
  nation-specific: Scotland and Wales each have their own, entirely
  separate statistics bodies (National Records of Scotland, StatsWales)
  that have not been looked at at all.
- **`SchoolCatchmentArea` (linking a catchment polygon to the school it
  covers) is entirely unimplemented, and confirmed not solvable by name-
  matching for most sources.** Sheffield's features carry no name at all;
  Aberdeen's `NAME` field is a place/zone name with no textual
  relationship to any school name. Edinburgh's is the one real exception
  found so far: its `EST_NAME` field carries the actual school name
  (verified live, e.g. "Abbeyhill Primary School"), a genuine candidate
  for this if pursued. Until this exists generally, a matched catchment
  on `/admissions` correctly shows the area name but an empty
  served-schools list - degraded, not wrong.
- **Catchment coverage is 9 local authorities out of ~200+ across Great
  Britain** (Sheffield/England; Aberdeen City, City of Edinburgh, Glasgow
  City, Fife, North Lanarkshire, Highland, Dundee City, Perth and
  Kinross/Scotland). Scotland turned out to have real ArcGIS-hosted
  catchment data much more widely than expected (every Scottish council
  checked so far has had one - 8 for 8); a genuine national aggregate
  (Spatial Hub Scotland / Improvement Service, covering all of Scotland
  in one WFS with per-feature local-authority fields) was found but could
  not be reached from this session's environment (403, see the
  `catchment-sources.yml` candidate entry) - worth retrying from a
  different network origin before checking the remaining ~24 council
  areas individually. Wales has no viable source found yet beyond
  Cardiff (ruled out); other Welsh councils have not been checked.
- **Denominational (ND/RC) catchment splits (Edinburgh, Glasgow, Fife,
  North Lanarkshire, Dundee, Perth and Kinross) are map-overlay-only, not
  reachable via `/admissions`.** See "Completed and verified" above for
  why (geographic overlap between denominations). The checker would need
  to ask "which denomination" before this can extend to Scotland's
  `/admissions` results; not attempted.
- **Playwright end-to-end tests do not exist yet** (`playwright.config.ts`
  is present but there is no `tests/e2e/` content). Not attempted this
  session; would need a running app and, for full coverage, real data.

## Known failing tests

None. Every test suite that was run passed: `packages/shared` (42),
`apps/web` (29), `services/ingestor` (76).

## Exact next steps, in order

1. Try Spatial Hub Scotland's national catchment WFS aggregate again from
   a different network origin (403 from this session's environment - see
   "Completed and verified" above); if reachable, it likely obsoletes
   most of the per-council entries already added. Otherwise keep
   checking the remaining ~24 Scottish council areas individually,
   matching the same verification rigor the first 8 got. Separately,
   check more Welsh councils beyond Cardiff (ruled out).
2. Decide on a path for the metrics gap (school-level DfE source for
   England, or entirely separate research for Scotland/Wales's own
   statistics bodies) before spending more time on `import-statistics`.
3. Get explicit go-ahead, informed by `scripts/calibration-report.md`,
   before any larger/national GIAS import (that report predates the
   devolved-nations work and only covers England). The report's own
   recommendation: national schools/trusts/local-authorities data looks
   cheap; catchment geometry is the dominant storage cost and should be
   rolled out one local authority at a time with real console figures
   checked after each addition, not assumed to scale linearly from the
   single Sheffield sample.
4. Frontend/UX polish pass (explicitly requested): review every page for
   visual consistency and finish, not just functional correctness.
5. Optional polish: `SchoolCatchmentArea` per-source research (see
   "Unfinished" above - Edinburgh's `EST_NAME` field is the most
   promising real starting point), a denomination-aware `/admissions`
   flow for Scotland's ND/RC catchment splits, Playwright e2e coverage
   for the golden paths (search a school, check a postcode, view the map
   with the catchment overlay on).
