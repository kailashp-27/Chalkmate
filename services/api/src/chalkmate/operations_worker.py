from sqlalchemy import text

from chalkmate.processing import engine
from chalkmate.worker import celery_app


@celery_app.task(name="chalkmate.worker_heartbeat")
def worker_heartbeat():
    with engine().begin() as db:
        db.execute(text("SELECT chalkmate.record_worker_heartbeat()"))
