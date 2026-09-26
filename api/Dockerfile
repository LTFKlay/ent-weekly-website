FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY api/pyproject.toml /app/
COPY api/src /app/src
COPY api/config /app/config
RUN pip install --no-cache-dir .
ENV PYTHONPATH=/app/src
CMD ["uvicorn", "ent_weekly.main:app", "--host", "0.0.0.0", "--port", "8080"]
