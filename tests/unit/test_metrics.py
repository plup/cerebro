"""Prometheus metrics tests."""

from datetime import datetime

from cerebro.metrics import prometheus_text, record_job_status
from cerebro.models.base import Worker
from cerebro.models.cortex import CortexJob


def test_metrics_keep_one_run_and_latest_status() -> None:
    worker = Worker(name='bar', type='analyzer', triggers=['observable:hostname'], manifest={})
    record_job_status(
        CortexJob(
            id='j1',
            worker=worker,
            object_type='observable:hostname',
            kube_status='Waiting',
            started=datetime.now(),
        )
    )
    record_job_status(
        CortexJob(
            id='j1',
            worker=worker,
            object_type='observable:hostname',
            kube_status='Success',
            started=datetime.now(),
            ended=datetime.now(),
        )
    )

    text = prometheus_text()
    assert (
        'cerebro_job_runs_total{worker="bar",invocation_type="analyzer"} 1'
    ) in text
    assert 'status="in_progress"' not in text
    assert (
        'cerebro_jobs{worker="bar",invocation_type="analyzer",status="success"} 1'
    ) in text


def test_metrics_use_worker_status_when_callback_reports_failure() -> None:
    worker = Worker(name='bar', type='analyzer', triggers=['observable:hostname'], manifest={})
    record_job_status(
        CortexJob(
            id='j2',
            worker=worker,
            object_type='observable:hostname',
            kube_status='Success',
            started=datetime.now(),
            ended=datetime.now(),
            callback_report={'success': False},
        )
    )

    assert (
        'cerebro_jobs{worker="bar",invocation_type="analyzer",status="failure"} 1'
    ) in prometheus_text()


def test_metrics_map_active_statuses_to_in_progress() -> None:
    worker = Worker(name='bar', type='analyzer', triggers=['observable:hostname'], manifest={})
    record_job_status(
        CortexJob(
            id='j3',
            worker=worker,
            object_type='observable:hostname',
            kube_status='InProgress',
            started=datetime.now(),
        )
    )

    assert (
        'cerebro_jobs{worker="bar",invocation_type="analyzer",status="in_progress"} 1'
    ) in prometheus_text()
