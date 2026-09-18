FROM node:24-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates tzdata && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 -o /usr/local/bin/supercronic && chmod +x /usr/local/bin/supercronic
WORKDIR /app
COPY web/package.json web/package-lock.json /app/web/
RUN cd /app/web && npm ci
COPY web /app/web
COPY cron /app/cron
RUN chmod +x /app/cron/jobs/*.sh /app/cron/entrypoint.sh
CMD ["/app/cron/entrypoint.sh"]
