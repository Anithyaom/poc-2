from celery import Celery

from src.config.settings import settings

app = Celery("simgen", broker=settings.broker_url, backend=settings.result_backend)

app.conf.update(
    task_acks_late=True,  # redeliver if a worker dies mid-task
    worker_prefetch_multiplier=1,  # long tasks: don't hoard the queue
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_default_queue="generation",
    task_routes={"src.tasks.*": {"queue": "generation"}},
)

app.autodiscover_tasks(["src.tasks"], force=True)

# Imports for side effect: register the tasks on this app instance.
import src.tasks.plan  # noqa: E402,F401
import src.tasks.simulation  # noqa: E402,F401
