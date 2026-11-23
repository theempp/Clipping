#!/usr/bin/env bash
# Apply stub + migrations + checks on a throwaway local Postgres. Usage: tests/run.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
bin="${PG_BIN:-$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)}"
tmp="$(mktemp -d)"; port="${PG_TEST_PORT:-55432}"
as() { if [ "$(id -u)" = 0 ]; then su postgres -s /bin/bash -c "$*"; else bash -c "$*"; fi; }
[ "$(id -u)" = 0 ] && chown postgres "$tmp"
as "$bin/initdb -D $tmp/db -U postgres -A trust >/dev/null"
as "$bin/pg_ctl -D $tmp/db -o '-p $port -k $tmp' -l $tmp/log start -w >/dev/null"
trap 'as "$bin/pg_ctl -D $tmp/db stop -m immediate >/dev/null"; rm -rf "$tmp"' EXIT
psql() { command psql -h "$tmp" -p "$port" -U postgres -v ON_ERROR_STOP=1 -q "$@"; }
psql -c "create database clipp_test"
psql -d clipp_test -f "$here/supabase_stub.sql"
for f in "$here"/../migrations/*.sql; do psql -d clipp_test -f "$f"; done
psql -d clipp_test -At -f "$here/core_test.sql"
psql -d clipp_test -At -f "$here/pods_test.sql"
