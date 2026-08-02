#!/usr/bin/env bash
# Rotates the school_ingestor password on the aqua-roach cluster and prints
# the resulting INGEST_DATABASE_URL to your own terminal only. This script
# never sends that value to Claude or writes it to a committed file. It also
# updates the GitHub secret of the same name, so GitHub Actions workflows
# keep working with the new password.
#
# Requires COCKROACH_BOOTSTRAP_URL, same as scripts/bootstrap-cockroachdb.sh:
# either exported in the calling shell or placed in a gitignored
# .env.cockroach.local file at the repo root.
#
# Usage:
#   COCKROACH_BOOTSTRAP_URL=... ./scripts/rotate-ingest-credential.sh
# or, with .env.cockroach.local already in place:
#   ./scripts/rotate-ingest-credential.sh

set -euo pipefail

DATABASE_NAME="school_intelligence"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOCAL_ENV_FILE="${REPO_ROOT}/.env.cockroach.local"

if [[ -z "${COCKROACH_BOOTSTRAP_URL:-}" && -f "${LOCAL_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${LOCAL_ENV_FILE}"
  set +a
fi

if [[ -z "${COCKROACH_BOOTSTRAP_URL:-}" ]]; then
  echo "COCKROACH_BOOTSTRAP_URL is not set. Either export it directly:" >&2
  echo '  COCKROACH_BOOTSTRAP_URL="<admin connection string>" ./scripts/rotate-ingest-credential.sh' >&2
  echo "or create ${LOCAL_ENV_FILE} containing:" >&2
  echo '  COCKROACH_BOOTSTRAP_URL="<admin connection string>"' >&2
  exit 1
fi

command -v psql >/dev/null 2>&1 || { echo "psql is required (CockroachDB is wire compatible with postgres)." >&2; exit 1; }
command -v gh >/dev/null 2>&1 || { echo "gh CLI is required to update the matching GitHub secret." >&2; exit 1; }

run_sql() {
  psql "$COCKROACH_BOOTSTRAP_URL" -v ON_ERROR_STOP=1 -X -q -c "$1"
}

if [[ "$COCKROACH_BOOTSTRAP_URL" != *"sslmode="* ]]; then
  echo "COCKROACH_BOOTSTRAP_URL has no explicit sslmode. Refusing to continue: CockroachDB Cloud connections must use TLS." >&2
  exit 1
fi

echo "Rotating school_ingestor password..."
NEW_PASSWORD="$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 40)"
run_sql "ALTER USER school_ingestor WITH PASSWORD '${NEW_PASSWORD}';"

HOST_PORT="$(echo "$COCKROACH_BOOTSTRAP_URL" | sed -E 's#^[a-zA-Z]+://[^@]*@([^/?]+).*#\1#')"
INGEST_DATABASE_URL="postgresql://school_ingestor:${NEW_PASSWORD}@${HOST_PORT}/${DATABASE_NAME}?sslmode=verify-full"
unset NEW_PASSWORD

echo "Testing the new credential..."
psql "$INGEST_DATABASE_URL" -v ON_ERROR_STOP=1 -X -q -c "SELECT 1;" >/dev/null
echo "New credential verified working."

echo "Updating the GitHub secret to match..."
printf '%s' "$INGEST_DATABASE_URL" | gh secret set INGEST_DATABASE_URL
echo "GitHub secret INGEST_DATABASE_URL updated."

echo ""
echo "Your new INGEST_DATABASE_URL (shown only here, in your own terminal):"
echo "  ${INGEST_DATABASE_URL}"
echo ""
echo "To run the ingestor locally against production, in this same terminal:"
echo '  cd services/ingestor'
echo '  source .venv/bin/activate   # or: python3 -m venv .venv && pip install -e . if not set up yet'
echo "  export INGEST_DATABASE_URL=\"${INGEST_DATABASE_URL}\""
echo '  ingestor import-gias --row-limit 10000'
echo '  ingestor import-trusts'
echo ""
echo "When done, in this terminal:"
echo "  unset INGEST_DATABASE_URL"
echo "  unset COCKROACH_BOOTSTRAP_URL"
