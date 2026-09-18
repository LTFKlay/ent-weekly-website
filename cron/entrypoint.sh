#!/bin/sh
set -eu

cd /app/web
npm run build
cp -R /app/dist/. /app/web_dist/
exec supercronic /app/cron/crontab
