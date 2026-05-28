"""
Celery worker configuration and task registration tests.

All tests here are synchronous — Celery config is plain Python,
no database or event loop needed.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def test_celery_broker_and_backend_url():
    """Broker and result backend must both point to REDIS_URL."""
    from app.workers.celery_app import app

    expected = os.environ["REDIS_URL"]
    assert app.conf.broker_url == expected
    assert app.conf.result_backend == expected


def test_celery_task_serializer_is_json():
    from app.workers.celery_app import app

    assert app.conf.task_serializer == "json"


def test_celery_timezone_is_utc():
    from app.workers.celery_app import app

    assert app.conf.timezone == "UTC"


def test_celery_task_track_started():
    from app.workers.celery_app import app

    assert app.conf.task_track_started is True


def test_index_repository_task_is_registered():
    """Importing tasks registers them; the named task must appear in app.tasks."""
    import app.workers.tasks  # noqa: F401 — side-effect: registers tasks

    from app.workers.celery_app import app as celery_app

    assert "app.workers.tasks.index_repository" in celery_app.tasks
