# Troubleshooting

## `prisma migrate deploy` fails in the migration workflow

* Confirm `MIGRATION_DATABASE_URL` is set as a GitHub secret and hasn't
  expired or been rotated on the CockroachDB side without updating the
  secret.
* Run `prisma migrate status` (the workflow does this first, before deploy)
  to see whether the drift is a pending migration or a genuinely diverged
  schema.
* Never resolve a stuck migration with a production reset. Write a new
  forward migration instead.

## `next build` fails on Prisma client generation

`prisma generate` for the CockroachDB provider needs a syntactically valid
`DATABASE_URL` at generate time even though it does not need a live
connection; CI sets a placeholder value for exactly this reason (see
`ci.yml`). If this fails locally, check that your `.env.local` has a
`DATABASE_URL` set, even a fake one, before running `pnpm db:generate`.

## Ingestion workflow reports `SKIPPED_UNCHANGED` every run

This is expected and correct when the upstream source hasn't republished.
Confirm with `--force` locally against a non-production database if you
need to re-verify parsing logic against the same file content.

## A catchment import fails partway through

By design, nothing is overwritten: the previous valid `CatchmentArea` rows
for that source remain live. Check the uploaded validation report artifact
from the `ingest-catchments` workflow run for per-feature rejection reasons
before re-running.

## `/status` shows a database connectivity failure

Check CockroachDB Cloud's own dashboard for the `aqua-roach` cluster first
(maintenance windows, connection limits) before assuming an application
bug. `/status` intentionally does not show the underlying error detail; if
you need the real error, check the Vercel function logs for the request ID
shown, or check server-side structured logs, never re-expose the raw error
to the page.

## A Vercel preview deployment can't reach the database

Confirm the `DATABASE_URL` environment variable is scoped to "Preview" as
well as "Production" in the Vercel project settings; Vercel environment
variables are scoped per environment and a variable added only for
Production will not be available to preview deployments.

## Local `docker compose` ingestion can't reach CockroachDB

The local `docker-compose.yml` insecure single-node CockroachDB is for local
development only; it is not the production `aqua-roach` cluster. Confirm
`INGEST_DATABASE_URL` in your local `.env` points at
`localhost:26257` with `sslmode=disable` for local runs, not a production
connection string.
