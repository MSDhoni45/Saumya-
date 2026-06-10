# ---- build stage -----------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime stage ---------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /install /usr/local
COPY ./app ./app

RUN chown -R app:app /app

USER app

EXPOSE 8000

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
