#!/usr/bin/env bash
# Build and start HuskyPoll with a freshly seeded demo database.
#
# Plain `docker compose up` is not affected: it keeps using the normal
# backend/data/huskypoll.db database (empty on a fresh checkout).
#
# Usage:
#   ./scripts/demo.sh          # build, reset the demo DB, seed it, start the app
#   docker compose up -d       # switch back to the normal database
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f compose.yml -f compose.demo.yml)
DEMO_DB=/data/huskypoll-demo.db

echo "Stopping the current stack..."
"${COMPOSE[@]}" down

echo "Building the images..."
"${COMPOSE[@]}" build

echo "Resetting the demo database..."
"${COMPOSE[@]}" run --rm backend sh -c \
  "rm -f ${DEMO_DB} ${DEMO_DB}-wal ${DEMO_DB}-shm"

echo "Seeding the demo course..."
"${COMPOSE[@]}" run --rm backend python -m app.database seed-demo

echo "Starting HuskyPoll with demo data..."
"${COMPOSE[@]}" up -d

cat <<'EOF'

HuskyPoll (demo data) is running at http://localhost:5173
Demo logins: prf00001 (instructor), tas00001 (TA), adm00001 (admin), ccb23028 (student)
Normal database is untouched. Switch back with: docker compose up -d
EOF
