# Workers

Celery workers handle background jobs that cannot run inside an HTTP request:
cloning repos, AST parsing, and generating embeddings.

## Prerequisites

Redis must be running. Start it from the repo root:

```bash
docker compose up -d redis
```

## Running the worker locally

From `backend/`:

**Windows:**
```bash
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

> Windows does not support Celery's default `prefork` pool because it relies on `os.fork()`, which is unavailable on Windows. The `solo` pool runs tasks in the same process as the worker, which works fine for local development.

**Linux / macOS / Docker (default prefork pool):**
```bash
celery -A app.workers.celery_app worker --loglevel=info
```

The worker connects to `REDIS_URL` from your `.env` file.

## Dispatching a task (from a Python shell)

```python
from app.workers.tasks import index_repository
result = index_repository.delay("https://github.com/org/repo", "some-job-uuid")
print(result.get(timeout=10))
```

## Monitoring (optional)

Install Flower in the venv, then:

```bash
celery -A app.workers.celery_app flower
```

Open http://localhost:5555 to see task queues and results.
