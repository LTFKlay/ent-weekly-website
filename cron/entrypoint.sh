#!/bin/sh
set -eu

cd /app/web
npm run build
rsync -a --delete /app/dist/ /app/web_dist/

# Keep scheduling inside the container so the image does not depend on a
# separately downloaded scheduler binary. TZ is supplied by docker-compose.
last_minute=""
run_job() {
  if ! "$@" >> /data/cron.log 2>&1; then
    printf '%s failed: %s\n' "$(date -Is)" "$*" >&2
  fi
}

while :; do
  current_minute="$(date +%Y-%m-%dT%H:%M)"
  if [ "$current_minute" != "$last_minute" ]; then
    last_minute="$current_minute"
    case "$(date +%u-%H:%M)" in
      *-14:00) run_job /app/cron/jobs/daily.sh ;;
      1-10:00) run_job /app/cron/jobs/backup.sh ;;
      1-19:00) run_job /app/cron/jobs/weekly.sh ;;
    esac
  fi
  sleep 20
done
