"""
Scheduler — runs periodic background jobs using APScheduler.

Started automatically in FastAPI's @app.on_event("startup").
Runs the evaluator every 4 hours to check past trade predictions.

Jobs:
  1. evaluate_pending_trades — every 4 hours
     Checks if trade predictions came true, generates lessons.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Module-level scheduler instance
_scheduler: BackgroundScheduler | None = None


def start_scheduler():
    """
    Initialize and start the background scheduler.
    Called once during FastAPI startup.
    """
    global _scheduler

    if _scheduler is not None:
        print("[Scheduler] Already running, skipping restart")
        return

    _scheduler = BackgroundScheduler()

    # Job 1: Evaluate pending trade predictions every 4 hours
    _scheduler.add_job(
        _run_evaluator,
        trigger=IntervalTrigger(hours=4),
        id="evaluator",
        name="Trade Prediction Evaluator",
        replace_existing=True,
    )

    _scheduler.start()
    print("[Scheduler] Started — evaluator runs every 4 hours")
    print(f"[Scheduler] Next run: {_scheduler.get_job('evaluator').next_run_time}")


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        print("[Scheduler] Stopped")


def _run_evaluator():
    """Wrapper that catches errors so the scheduler doesn't die."""
    try:
        from backend.jobs.evaluator import evaluate_pending_trades
        print("\n[Scheduler] Running evaluator...")
        result = evaluate_pending_trades()
        print(f"[Scheduler] Evaluator done: {result}")
    except Exception as e:
        print(f"[Scheduler] Evaluator error: {e}")


def get_scheduler_status() -> dict:
    """Get current scheduler status and next run times."""
    if not _scheduler:
        return {"running": False}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })

    return {"running": True, "jobs": jobs}
