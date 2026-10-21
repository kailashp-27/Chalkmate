from celery import Celery

from chalkmate.config import get_settings

celery_app = Celery(
    "chalkmate",
    broker=get_settings().celery_broker_url,
    include=[
        "chalkmate.processing",
        "chalkmate.followup_worker",
        "chalkmate.intelligence_worker",
        "chalkmate.planning_worker",
        "chalkmate.operations_worker",
    ],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    enable_utc=True,
    timezone="UTC",
    broker_connection_retry_on_startup=True,
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "worker-heartbeat": {"task": "chalkmate.worker_heartbeat", "schedule": 15.0},
        "dispatch-planning": {"task": "chalkmate.dispatch_planning", "schedule": 5.0},
        "dispatch-teaching-intelligence": {
            "task": "chalkmate.dispatch_intelligence",
            "schedule": 5.0,
        },
        "dispatch-durable-jobs": {"task": "chalkmate.dispatch_pending", "schedule": 5.0},
        "dispatch-recipient-outbox": {"task": "chalkmate.dispatch_deliveries", "schedule": 5.0},
    },
)
