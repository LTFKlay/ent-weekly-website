#!/bin/sh
set -eu

# PubMed EDAT rolls on the U.S. East Coast. 14:00 Shanghai is after the
# previous complete Eastern day has closed.
TARGET=$(TZ=America/New_York date -d 'yesterday' +%F)
curl -fsS -X POST http://api:8080/internal/run-daily \
  -H "Authorization: Bearer ${REGEN_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "{\"target_edat\":\"${TARGET}\"}"

cd /app/web
npm run build
cp -R /app/dist/. /app/web_dist/
