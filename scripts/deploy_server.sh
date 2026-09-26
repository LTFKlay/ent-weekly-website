#!/bin/sh
set -eu

usage() {
  echo "用法: $0 [--rescreen]" >&2
  echo "  --rescreen  部署后全量重筛公开文献并重建已有周报。" >&2
  exit 2
}

case "${1:-}" in
  "")
    rescreen=false
    ;;
  --rescreen)
    rescreen=true
    ;;
  *)
    usage
    ;;
esac

docker compose up -d --build api cron web

if [ "$rescreen" = true ]; then
  docker compose exec -T api python -m ent_weekly.rescreen
  docker compose exec -T api python -m ent_weekly.rescreen --apply --reclassify --refresh-weekly
fi

docker compose exec -T cron sh -lc 'cd /app/web && npm run build && rsync -a --delete /app/dist/ /app/web_dist/'
docker compose exec -T api python -c 'from ent_weekly.policy import SCREENING_POLICY_VERSION; print(SCREENING_POLICY_VERSION)'
