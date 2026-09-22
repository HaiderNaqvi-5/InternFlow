#!/bin/sh
# Wait for the PostgreSQL server to accept connections before starting the API.
set -eu

HOST="${PGHOST:-db}"
PORT="${PGPORT:-5432}"
ATTEMPTS="${DB_WAIT_ATTEMPTS:-30}"
INTERVAL="${DB_WAIT_INTERVAL:-2}"

i=0
while [ "$i" -lt "$ATTEMPTS" ]; do
    if nc -z "$HOST" "$PORT" 2>/dev/null; then
        echo "Database is available at $HOST:$PORT"
        exit 0
    fi
    if command -v pg_isready >/dev/null 2>&1 && pg_isready -h "$HOST" -p "$PORT" -q 2>/dev/null; then
        echo "Database is available at $HOST:$PORT"
        exit 0
    fi
    i=$((i + 1))
    echo "Waiting for database at $HOST:$PORT ($i/$ATTEMPTS)..."
    sleep "$INTERVAL"
done

echo "Database did not become available in time" >&2
exit 1