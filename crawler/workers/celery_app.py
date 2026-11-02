"""Celery application configuration for the Aegyptus crawler."""

import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "aegyptus_crawler",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["crawler.workers.tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="crawl",
    task_default_rate_limit="10/m",
    task_soft_time_limit=120,
    task_time_limit=180,
    worker_concurrency=4,
)
