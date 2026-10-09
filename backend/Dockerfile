# LinguaSI API (FastAPI). Build from the repository root so the seed content and migrations are included:
#   docker build -f backend/Dockerfile -t linguasi-api .
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
# Alembic migrations and curated seed content live in /database at the repository root.
COPY database/ /app/database/

RUN useradd --create-home --uid 10001 linguasi \
    && mkdir -p /app/backend/storage \
    && chown linguasi /app/backend/storage
USER linguasi

ENV ENVIRONMENT=production \
    STORAGE_LOCAL_DIR=/app/backend/storage \
    PORT=8000 \
    FORWARDED_ALLOW_IPS=127.0.0.1
EXPOSE 8000

# Apply database migrations, then serve. Uvicorn trusts X-Forwarded-For only from FORWARDED_ALLOW_IPS
# (set it to your reverse proxy / web server addresses), so clients cannot spoof their IP.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips \"$FORWARDED_ALLOW_IPS\""]
