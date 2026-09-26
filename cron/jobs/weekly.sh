#!/bin/sh
set -eu

WEEK_END=$(date -d 'yesterday' +%F)
WEEK_START=$(date -d '7 days ago' +%F)
curl -fsS -X POST http://api:8080/internal/run-weekly \
  -H "Authorization: Bearer ${REGEN_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "{\"week_start\":\"${WEEK_START}\",\"week_end\":\"${WEEK_END}\"}"

cd /app/web
npm run build
rsync -a --delete /app/dist/ /app/web_dist/
