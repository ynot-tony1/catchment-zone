# Deployment

## Overview

Application hosting is Vercel. Source control, CI, and scheduled or manual
data jobs are GitHub Actions. The database is CockroachDB Cloud. Nothing here
requires a developer's machine to stay on after the initial setup below.

## One-time setup

### 1. GitHub

```bash
gh auth status               # confirm you're logged in
gh repo create <owner>/catchment-zone --private --source=. --remote=origin
git push -u origin main
```

Then configure secrets and variables (values are entered interactively by
the CLI prompt or the GitHub web UI, never passed as a plain command
argument):

```bash
gh secret set INGEST_DATABASE_URL
gh secret set MIGRATION_DATABASE_URL
gh variable set INGESTION_ENABLED --body true
gh variable set CATCHMENT_INGESTION_ENABLED --body true
```

### 2. CockroachDB Cloud

See `scripts/bootstrap-cockroachdb.sh` and `docs/operations.md`. Summary: a
short-lived `COCKROACH_BOOTSTRAP_URL` environment variable, set only in your
own shell (never pasted into any chat tool), is used once to create the
`school_intelligence` database and the three scoped SQL users described in
`docs/database.md`. The script prints nothing secret; it writes the three
resulting scoped connection strings directly into GitHub secrets and Vercel
environment variables via `gh` and `vercel` CLI calls, then the operator
unsets the bootstrap variable.

### 3. Vercel

```bash
vercel login
vercel link                  # link this directory to the catchment-zone project
```

In the Vercel project settings (or via `vercel env add`):

- Root directory: `apps/web`
- `DATABASE_URL`: the `school_app` scoped connection string, added as a
  secret environment variable (Production and Preview)
- Public config, non-secret: `NEXT_PUBLIC_SITE_URL`,
  `NEXT_PUBLIC_MAP_STYLE_URL`, `NEXT_PUBLIC_MAP_ATTRIBUTION`,
  `POSTCODE_GEOCODER`, `CATCHMENT_BOUNDARY_WARNING_METRES`, `LOG_LEVEL`

Connect the project to the GitHub repository through Vercel's native GitHub
integration so pull requests get preview deployments automatically and
merges to `main` deploy to production. Do not configure a separate custom CI
deploy step; let Vercel's GitHub integration own this.

### 4. First migration

Run the `migrate-production` workflow manually from the Actions tab (or `gh
workflow run migrate-production.yml -f confirm=migrate`) once
`MIGRATION_DATABASE_URL` is set. This applies the initial schema to
`school_intelligence`.

## Ongoing deployment flow

- Every pull request gets a Vercel preview deployment and a CI run.
- Merging to `main` triggers a Vercel production deployment.
- Schema changes require a manual run of `migrate-production.yml` before (or
  as part of, if the migration is backward compatible) merging the
  application code that depends on the new schema.
- Ingestion is entirely scheduled/manual GitHub Actions; it does not run as
  part of the Vercel build.

## Rollback

Vercel keeps prior production deployments; promote a previous deployment
from the Vercel dashboard or `vercel rollback` if a production deploy needs
to be reverted. Database migrations are not automatically reversible; a
schema rollback requires a new forward migration, not a destructive reset.
