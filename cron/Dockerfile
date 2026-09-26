FROM node:24-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates rsync tzdata && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY web/package.json web/package-lock.json /app/web/
RUN cd /app/web && npm ci
COPY web /app/web
COPY cron /app/cron
RUN chmod +x /app/cron/jobs/*.sh /app/cron/entrypoint.sh
CMD ["/app/cron/entrypoint.sh"]
