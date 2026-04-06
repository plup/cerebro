"""In-memory store for job results posted back from worker pods via HTTP callback.

This is process-local: multiple Cerebro replicas each keep a separate store; use one replica or
add shared storage if you need cross-replica callbacks.
"""

from threading import Lock
from typing import Any

_lock = Lock()
_reports: dict[str, dict[str, Any]] = {}


def store_job_report(job_id: str, report: dict[str, Any]) -> None:
    """Record a Cortex-shaped report dict for a completed job (last write wins)."""
    with _lock:
        _reports[job_id] = report


def get_stored_report(job_id: str) -> dict[str, Any] | None:
    """Return a previously stored report, if any."""
    with _lock:
        return _reports.get(job_id)
