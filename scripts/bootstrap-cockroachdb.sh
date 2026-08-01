#!/usr/bin/env bash
# Bootstraps the school_intelligence database and its three scoped SQL users
# on the aqua-roach CockroachDB Cloud cluster.
#
# Requires COCKROACH_BOOTSTRAP_URL, either exported in the calling shell or
# placed in a gitignored .env.cockroach.local file at the repo root (see
# .gitignore's ".env.*.local" rule). This script never echoes, logs, or
# writes that value, or any generated password, to disk or stdout. It writes
# the three resulting scoped connection strings directly into GitHub secrets
# and Vercel environment variables via the gh and vercel CLIs, then reminds
# you to unset COCKROACH_BOOTSTRAP_URL yourself if it came from your shell.
#
# Usage:
#   COCKROACH_BOOTSTRAP_URL=... ./scripts/bootstrap-cockroachdb.sh
# or, with .env.cockroach.local already in place:
#   ./scripts/bootstrap-cockroachdb.sh

set -euo pipefail

DATABASE_NAME="school_intelligence"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOCAL_ENV_FILE="${REPO_ROOT}/.env.cockroach.local"

# Convenience path: if COCKROACH_BOOTSTRAP_URL was not already exported in
# this shell, but a gitignored .env.cockroach.local file exists at the repo
# root, source just that one variable from it. Nothing from this file is
# ever echoed, logged, or written back out by this script.
if [[ -z "${COCKROACH_BOOTSTRAP_URL:-}" && -f "${LOCAL_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${LOCAL_ENV_FILE}"
  set +a
fi

if [[ -z "${COCKROACH_BOOTSTRAP_URL:-}" ]]; then
  echo "COCKROACH_BOOTSTRAP_URL is not set. Either export it directly:" >&2
  echo '  COCKROACH_BOOTSTRAP_URL="<admin connection string>" ./scripts/bootstrap-cockroachdb.sh' >&2
  echo "or create ${LOCAL_ENV_FILE} containing:" >&2
  echo '  COCKROACH_BOOTSTRAP_URL="<admin connection string>"' >&2
  exit 1
fi

command -v psql >/dev/null 2>&1 || { echo "psql is required (CockroachDB is wire compatible with postgres)." >&2; exit 1; }
command -v gh >/dev/null 2>&1 || { echo "gh CLI is required to store generated secrets." >&2; exit 1; }
command -v vercel >/dev/null 2>&1 || { echo "vercel CLI is required to store the application DATABASE_URL." >&2; exit 1; }

run_sql() {
  psql "$COCKROACH_BOOTSTRAP_URL" -v ON_ERROR_STOP=1 -X -q -c "$1"
}

echo "Verifying TLS and connectivity..."
if [[ "$COCKROACH_BOOTSTRAP_URL" != *"sslmode="* ]]; then
  echo "COCKROACH_BOOTSTRAP_URL has no explicit sslmode. Refusing to continue: CockroachDB Cloud connections must use TLS." >&2
  exit 1
fi
run_sql "SELECT 1;" >/dev/null
echo "Connectivity confirmed."

echo "Inspecting current privileges of the bootstrap role..."
run_sql "SHOW GRANTS;" >/dev/null

echo "Ensuring database ${DATABASE_NAME} exists..."
run_sql "CREATE DATABASE IF NOT EXISTS ${DATABASE_NAME};"

gen_password() {
  openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 40
}

MIGRATOR_PASSWORD="$(gen_password)"
INGESTOR_PASSWORD="$(gen_password)"
APP_PASSWORD="$(gen_password)"

echo "Creating scoped SQL users (passwords generated, not displayed)..."
run_sql "CREATE USER IF NOT EXISTS school_migrator WITH PASSWORD '${MIGRATOR_PASSWORD}';"
run_sql "CREATE USER IF NOT EXISTS school_ingestor WITH PASSWORD '${INGESTOR_PASSWORD}';"
run_sql "CREATE USER IF NOT EXISTS school_app WITH PASSWORD '${APP_PASSWORD}';"

echo "Applying least-privilege grants..."
# school_migrator: schema owner within the database, no user management.
run_sql "GRANT ALL ON DATABASE ${DATABASE_NAME} TO school_migrator;"

# school_ingestor: read/write data, no schema changes.
run_sql "GRANT CONNECT ON DATABASE ${DATABASE_NAME} TO school_ingestor;"
run_sql "GRANT USAGE ON SCHEMA public TO school_ingestor;"
run_sql "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO school_ingestor;"
run_sql "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO school_ingestor;"

# school_app: read everything, write only to postcode_cache.
run_sql "GRANT CONNECT ON DATABASE ${DATABASE_NAME} TO school_app;"
run_sql "GRANT USAGE ON SCHEMA public TO school_app;"
run_sql "GRANT SELECT ON ALL TABLES IN SCHEMA public TO school_app;"
run_sql "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO school_app;"
run_sql "GRANT SELECT, INSERT, UPDATE, DELETE ON postcode_cache TO school_app;" || \
  echo "Note: postcode_cache table does not exist yet; its grant to school_app will need to be re-run after the first migration." >&2

HOST_PORT="$(echo "$COCKROACH_BOOTSTRAP_URL" | sed -E 's#^[a-zA-Z]+://[^@]*@([^/?]+).*#\1#')"

MIGRATION_DATABASE_URL="postgresql://school_migrator:${MIGRATOR_PASSWORD}@${HOST_PORT}/${DATABASE_NAME}?sslmode=verify-full"
INGEST_DATABASE_URL="postgresql://school_ingestor:${INGESTOR_PASSWORD}@${HOST_PORT}/${DATABASE_NAME}?sslmode=verify-full"
DATABASE_URL="postgresql://school_app:${APP_PASSWORD}@${HOST_PORT}/${DATABASE_NAME}?sslmode=verify-full"

echo "Testing each scoped user can connect..."
psql "$MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -X -q -c "SELECT 1;" >/dev/null
psql "$INGEST_DATABASE_URL" -v ON_ERROR_STOP=1 -X -q -c "SELECT 1;" >/dev/null
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -X -q -c "SELECT 1;" >/dev/null
echo "All three scoped users connect successfully."

echo "Writing MIGRATION_DATABASE_URL and INGEST_DATABASE_URL to GitHub secrets..."
printf '%s' "$MIGRATION_DATABASE_URL" | gh secret set MIGRATION_DATABASE_URL
printf '%s' "$INGEST_DATABASE_URL" | gh secret set INGEST_DATABASE_URL

echo "Writing DATABASE_URL to Vercel (Production and Preview)..."
printf '%s' "$DATABASE_URL" | vercel env add DATABASE_URL production
printf '%s' "$DATABASE_URL" | vercel env add DATABASE_URL preview

unset MIGRATOR_PASSWORD INGESTOR_PASSWORD APP_PASSWORD
unset MIGRATION_DATABASE_URL INGEST_DATABASE_URL DATABASE_URL

echo ""
echo "Bootstrap complete. Now run in your own shell:"
echo "  unset COCKROACH_BOOTSTRAP_URL"
