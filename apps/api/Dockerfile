# Build context: repository root (migrations live outside apps/api).
#   docker build -f apps/api/Dockerfile .
# ---- build stage -----------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime stage ---------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /install /usr/local
COPY apps/api/app ./app
COPY apps/api/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY supabase/migrations ./supabase/migrations

RUN chmod +x /usr/local/bin/docker-entrypoint.sh && chown -R app:app /app

USER app

EXPOSE 8000

# Runs migrations first when RUN_MIGRATIONS=1 (API service only), then execs CMD.
ENTRYPOINT ["docker-entrypoint.sh"]

# Default: API server.
# Worker override: ["celery", "-A", "app.workers.celery_app.celery_app", "worker", ...]
# Beat override:   ["celery", "-A", "app.workers.celery_app.celery_app", "beat", ...]
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
