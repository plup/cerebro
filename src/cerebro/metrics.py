"""Prometheus metrics for Cerebro job runs."""

from __future__ import annotations

from collections import Counter
from threading import Lock
from typing import Any

_lock = Lock()
_runs: Counter[tuple[str, str]] = Counter()
_jobs: dict[str, tuple[str, str, str]] = {}


def record_job_status(job: Any) -> None:
    """Record the latest observed status for a Cerebro job."""
    status = _status_label(getattr(job, 'status', job.kube_status))
    run_labels = (job.worker.name, job.worker.type)
    status_labels = (*run_labels, status)
    with _lock:
        if job.id not in _jobs:
            _runs[run_labels] += 1
        _jobs[job.id] = status_labels


def prometheus_text() -> str:
    """Return job metrics in Prometheus text exposition format."""
    with _lock:
        runs = dict(_runs)
        jobs = Counter(_jobs.values())

    lines = [
        '# HELP cerebro_job_runs_total Cerebro jobs observed by worker and invocation type.',
        '# TYPE cerebro_job_runs_total counter',
    ]
    for (worker, invocation_type), value in sorted(runs.items()):
        labels = _labels(
            worker=worker,
            invocation_type=invocation_type,
        )
        lines.append(f'cerebro_job_runs_total{{{labels}}} {value}')

    lines.extend(
        [
            '# HELP cerebro_jobs Cerebro jobs grouped by latest observed worker status.',
            '# TYPE cerebro_jobs gauge',
        ]
    )
    for (worker, invocation_type, status), value in sorted(jobs.items()):
        labels = _labels(
            worker=worker,
            invocation_type=invocation_type,
            status=status,
        )
        lines.append(f'cerebro_jobs{{{labels}}} {value}')

    return '\n'.join(lines) + '\n'


def reset_metrics() -> None:
    """Clear process-local metrics state."""
    with _lock:
        _runs.clear()
        _jobs.clear()


def _status_label(status: str) -> str:
    return 'in_progress' if status in ('Waiting', 'InProgress') else status.lower()


def _labels(**labels: str) -> str:
    return ','.join(f'{name}="{_escape(value)}"' for name, value in labels.items())


def _escape(value: str) -> str:
    return str(value).replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
