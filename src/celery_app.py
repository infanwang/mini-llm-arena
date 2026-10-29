import os

from celery import Celery
from celery.schedules import crontab

from src.logging_config import configure

configure()

app = Celery("arena", broker=os.environ["REDIS_URL"], backend=os.environ["REDIS_URL"])
app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    beat_schedule={
        "weekly-consistency-check": {
            "task": "src.tasks.consistency_check",
            "schedule": crontab(hour=3, minute=0, day_of_week="mon"),
        },
    },
)

from src import tasks  # noqa: E402,F401
