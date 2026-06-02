"""
Celery app configuration for TWHC file processing pipeline.

# Last Update: 2026-03-26 20:30:00
# Author: Daniel Chung
# Version: 1.1.0
"""

import os
import sys

_AISERVICES_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AISERVICES_DIR not in sys.path:
    sys.path.insert(0, _AISERVICES_DIR)

os.environ.setdefault("API_ROOT", "/Users/daniel/GitHub/AIBox-TH/api")
os.environ["PYTHONPATH"] = (
    _AISERVICES_DIR + os.pathsep + os.environ.get("PYTHONPATH", "")
)

from celery import Celery  # noqa: E402
from celery.signals import worker_process_init  # noqa: E402

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "aibox-th",
    broker=REDIS_URL,
    include=["celery_app.tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Taipei",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check-scheduled-reports": {
            "task": "celery_app.tasks.check_scheduled_reports",
            "schedule": 60.0,
        },
    },
)


@worker_process_init.connect
def _fix_path(**_kwargs: object) -> None:
    if _AISERVICES_DIR not in sys.path:
        sys.path.insert(0, _AISERVICES_DIR)
