"""
Celery app: makes /profile/analyze non-blocking. The pipeline now includes
GitHub calls, resume parsing, three DSA source calls, and an LLM call -
easily 3-8s combined. Without a queue, that's 3-8s of blocked HTTP
connection per request.
"""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "engineeros",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
)
