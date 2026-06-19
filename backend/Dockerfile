FROM python:3.11-slim

WORKDIR /app

# git is required for the shallow clone in the indexing pipeline.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Base requirements only — no torch/sentence-transformers. Production uses the
# OpenAI embedder (EMBEDDING_PROVIDER=openai); the local stack lives in
# requirements-local.txt for dev.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run migrations, then boot on Railway's injected $PORT (default 8000 locally).
# Exec form wrapping `sh -c` so ${PORT} is expanded and && works, without the
# JSONArgsRecommended warning. The Celery worker runs as a separate service with
# the DEFAULT prefork pool (no --pool=solo — that's Windows-local-only).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
