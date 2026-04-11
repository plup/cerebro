"""In-memory store for job results posted back from worker pods via HTTP callback.

This is process-local: multiple Cerebro replicas each keep a separate store; use one replica or
add shared storage if you need cross-replica callbacks.
"""

from datetime import datetime
from threading import Lock
from typing import Any

_lock = Lock()
_reports: dict[str, dict[str, Any]] = {}
# Jobs that never reached Kubernetes (e.g. admission denied); keyed by job id returned to TheHive.
_synthetic_failed_jobs: dict[str, dict[str, Any]] = {}


def store_job_report(job_id: str, report: dict[str, Any]) -> None:
    """Record a Cortex-shaped report dict for a completed job (last write wins)."""
    with _lock:
        _reports[job_id] = report


def get_job_report(job_id: str) -> dict[str, Any] | None:
    """Return the callback report for a job id, if one was stored."""
    with _lock:
        return _reports.get(job_id)


def store_synthetic_failed_job(
    job_id: str,
    *,
    worker: dict[str, Any],
    object_type: str,
    started: datetime,
    ended: datetime | None,
    callback_report: dict[str, Any],
) -> None:
    """Remember a failed local job so ``fetch`` / ``waitreport`` can rebuild the Cortex job."""
    with _lock:
        _synthetic_failed_jobs[job_id] = {
            'worker': worker,
            'object_type': object_type,
            'started': started.isoformat(),
            'ended': ended.isoformat() if ended else '',
            'callback_report': callback_report,
        }


def get_synthetic_failed_job(job_id: str) -> dict[str, Any] | None:
    """Return stored payload for a synthetic failed job, if any."""
    with _lock:
        return _synthetic_failed_jobs.get(job_id)
