"""
OmniCore — Sync Engine
Manages automatic dataset synchronisation.
Each dataset has a configurable sync frequency (daily/weekly/monthly/manual).
The sync engine checks which datasets are due and triggers acquisition.
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from acquisition import run_acquisition
from auth import get_current_user
from database import db_session, get_db
from models import Dataset, SyncLog, User
from utils import Timer, success_response

logger = logging.getLogger("omnicore.sync")


# ── Sync Frequency Helpers ────────────────────────────────────────────────────

FREQUENCY_DELTA: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
    "yearly": timedelta(days=365),
    "quarterly": timedelta(days=90),
    "manual": timedelta(days=36500),  # Effectively never auto-syncs
}


def _is_due(dataset: Dataset) -> bool:
    """Return True if the dataset's next_sync is overdue."""
    if dataset.sync_frequency == "manual":
        return False
    if dataset.next_sync is None:
        return True
    return datetime.utcnow() >= dataset.next_sync


def _compute_next_sync(frequency: str) -> datetime:
    delta = FREQUENCY_DELTA.get(frequency, timedelta(weeks=1))
    return datetime.utcnow() + delta


# ── Sync Worker ───────────────────────────────────────────────────────────────

def _sync_worker(dataset_slug: str) -> None:
    """
    Background thread target.
    Runs acquisition for a single dataset and updates next_sync.
    """
    logger.info("Starting sync for dataset: %s", dataset_slug)
    success = run_acquisition(dataset_slug)

    with db_session() as db:
        dataset = db.query(Dataset).filter_by(slug=dataset_slug).first()
        if dataset:
            dataset.next_sync = _compute_next_sync(dataset.sync_frequency)
            if success:
                logger.info("Sync succeeded for %s. Next sync: %s", dataset_slug, dataset.next_sync)
            else:
                logger.warning("Sync failed for %s.", dataset_slug)


def sync_dataset(slug: str) -> threading.Thread:
    """
    Trigger an asynchronous sync for a dataset.
    Returns the thread (already started).
    """
    thread = threading.Thread(target=_sync_worker, args=(slug,), daemon=True, name=f"sync-{slug}")
    thread.start()
    return thread


# ── Scheduled Sync Runner ─────────────────────────────────────────────────────

class SyncScheduler:
    """
    Background scheduler that wakes periodically and syncs overdue datasets.
    Runs in a daemon thread; does not block the FastAPI event loop.
    """

    def __init__(self, check_interval_seconds: int = 3600):
        self.check_interval = check_interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="sync-scheduler",
        )
        self._thread.start()
        logger.info("Sync scheduler started (interval: %ds).", self.check_interval)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Sync scheduler stopped.")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._check_and_sync()
            self._stop_event.wait(timeout=self.check_interval)

    def _check_and_sync(self) -> None:
        try:
            with db_session() as db:
                due_datasets = (
                    db.query(Dataset)
                    .filter_by(is_active=True)
                    .filter(Dataset.sync_frequency != "manual")
                    .all()
                )
                to_sync = [ds.slug for ds in due_datasets if _is_due(ds)]

            if not to_sync:
                logger.debug("No datasets due for sync.")
                return

            logger.info("Syncing %d overdue dataset(s): %s", len(to_sync), to_sync)
            for slug in to_sync:
                sync_dataset(slug)
                time.sleep(2)  # Stagger starts to avoid API rate limits

        except Exception as exc:
            logger.error("Sync scheduler error: %s", exc)


# Global scheduler instance (lifecycle managed by main.py)
scheduler = SyncScheduler(check_interval_seconds=3600)


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/sync", tags=["Sync"])


@router.post("/{slug}")
def trigger_sync(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually trigger a sync for a specific dataset.
    Starts asynchronously; returns immediately.
    """
    dataset = db.query(Dataset).filter_by(slug=slug, is_active=True).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    # Check if already syncing
    running = db.query(SyncLog).filter_by(dataset_id=dataset.id, status="running").first()
    if running:
        return success_response(message="Sync already in progress for this dataset.")

    sync_dataset(slug)

    return success_response(
        message=f"Sync started for '{dataset.name}'. Check /sync/{slug}/status for progress.",
    )


@router.get("/{slug}/status")
def get_sync_status(
    slug: str,
    db: Session = Depends(get_db),
):
    """Get the most recent sync log entry for a dataset."""
    with Timer() as t:
        dataset = db.query(Dataset).filter_by(slug=slug, is_active=True).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found.")

        latest_log = (
            db.query(SyncLog)
            .filter_by(dataset_id=dataset.id)
            .order_by(SyncLog.started_at.desc())
            .first()
        )

    return success_response(
        data={
            "dataset_slug": slug,
            "dataset_name": dataset.name,
            "last_sync": dataset.last_sync.isoformat() + "Z" if dataset.last_sync else None,
            "next_sync": dataset.next_sync.isoformat() + "Z" if dataset.next_sync else None,
            "sync_frequency": dataset.sync_frequency,
            "processing_status": dataset.processing_status,
            "latest_log": {
                "status": latest_log.status,
                "started_at": latest_log.started_at.isoformat() + "Z",
                "completed_at": latest_log.completed_at.isoformat() + "Z" if latest_log.completed_at else None,
                "records_before": latest_log.records_before,
                "records_after": latest_log.records_after,
                "error": latest_log.error_message,
            } if latest_log else None,
        },
        execution_time_ms=t.elapsed_ms,
    )


@router.get("/")
def list_sync_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Return recent sync history across all datasets."""
    with Timer() as t:
        from utils import paginate
        offset, limit = paginate(page, page_size)
        total = db.query(SyncLog).count()
        logs = (
            db.query(SyncLog)
            .order_by(SyncLog.started_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    return success_response(
        data=[
            {
                "id": log.id,
                "dataset_id": log.dataset_id,
                "status": log.status,
                "started_at": log.started_at.isoformat() + "Z",
                "completed_at": log.completed_at.isoformat() + "Z" if log.completed_at else None,
                "records_before": log.records_before,
                "records_after": log.records_after,
                "error": log.error_message,
            }
            for log in logs
        ],
        count=len(logs),
        total=total,
        page=page,
        execution_time_ms=t.elapsed_ms,
    )
