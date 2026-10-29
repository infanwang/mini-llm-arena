import structlog

from src.celery_app import app

log = structlog.get_logger()


@app.task(name="src.tasks.consistency_check")
def consistency_check() -> dict:
    from jobs.run_consistency import run_consistency_check

    result = run_consistency_check()
    log.info("consistency_check_done", **result)
    return result
