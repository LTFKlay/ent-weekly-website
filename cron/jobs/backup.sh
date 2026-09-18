#!/bin/sh
set -eu
mkdir -p /data/backups
stamp=$(date +%F)
test -f /data/ent_weekly.db && cp /data/ent_weekly.db "/data/backups/ent_weekly-${stamp}.db"
find /data/backups -type f -name 'ent_weekly-*.db' -mtime +30 -delete

