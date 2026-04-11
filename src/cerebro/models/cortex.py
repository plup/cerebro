"""Cortex-compatible façade over ``cerebro.models.base``.

Cerebro is an in-place replacement for Cortex. The base model layer contains all and only what
Cerebro needs to operate; this module extends those types so responses and job objects match what
Cortex exposes (e.g. analyzers, responders, and ``CortexJob`` for TheHive).
"""
from datetime import datetime, timezone

from pydantic import Field, computed_field
from .base import Worker, K8sJob

# Shown in ``report`` when the job finished without a callback payload (Cortex-compatible text).
NO_CALLBACK_REPORT_MESSAGE = 'No report has been generated.'

# Minimal manifest so :class:`Worker` validates when building a job-only error response.
_FETCH_FAILURE_WORKER_MANIFEST = {
    'apiVersion': 'batch/v1',
    'kind': 'Job',
    'metadata': {'generateName': 'cerebro-fetch-error-'},
    'spec': {
        'template': {
            'spec': {
                'restartPolicy': 'Never',
                'containers': [{'name': 'job', 'image': 'invalid.invalid/cerebro-placeholder'}],
            }
        }
    },
}


class Analyzer(Worker):
    @computed_field
    @property
    def dataTypeList(self) -> list[str]:
        """Analyzers only run on observables. Use the triggers to build the compatible list"""
        return [f.split(':')[1] for f in self.triggers]

    @classmethod
    def listall(cls):
        """Return only analyzers."""
        return cls.search(type='analyzer')


class Responder(Worker):
    @computed_field
    @property
    def dataTypeList(self) -> list[str]:
        """Responders currently only support observables."""
        return ["thehive:case_artifact"]

    @classmethod
    def listall(cls):
        """Return only responders."""
        return cls.search(type='responder')


class CortexJob(K8sJob):
    """
    Flatten related object properties to behave like Cortex.

    A CortexJob has all the properties required by TheHive.

    ``kube_status`` is the Kubernetes Batch Job state (omitted from JSON for TheHive). ``status``
    follows the callback report's ``success`` when a payload was posted; otherwise it matches
    ``kube_status``.
    """
    worker: Worker = Field(exclude=True)
    kube_status: str = Field(exclude=True)
    organization: str = '' # Cortex normally returns organization but it's apparently not checked by TheHive

    @classmethod
    def from_fetch_failure(cls, job_id: str, message: str) -> 'CortexJob':
        """
        Build a terminal Failure job when the cluster job cannot be read (missing id, API error, bad annotations).

        TheHive still gets HTTP 200 with ``status`` / ``report`` describing the error.
        """
        now = datetime.now(timezone.utc)
        stub = Worker(
            name='cerebro-fetch-error',
            type='analyzer',
            triggers=[],
            manifest=_FETCH_FAILURE_WORKER_MANIFEST,
        )
        report = {'success': False, 'errorMessage': message}
        return cls(
            id=job_id,
            worker=stub,
            object_type='',
            kube_status='Failure',
            started=now,
            ended=now,
            callback_report=report,
        )

    @computed_field
    @property
    def status(self) -> str:
        """
        Status exposed to TheHive: from the callback ``success`` field when a report exists;
        otherwise ``kube_status`` (still ``Waiting`` / ``InProgress`` while the pod runs).
        """
        ks = self.kube_status
        if ks in ('Waiting', 'InProgress'):
            return ks
        if self.callback_report is not None:
            cr = self.callback_report
            if 'success' in cr:
                return 'Success' if cr['success'] else 'Failure'
            return 'Success' if ks == 'Success' else 'Failure'
        return ks

    @computed_field
    @property
    def dataType(self) -> str:
        """
        Short Cortex type for TheHive (``hostname``, ``ip``, …). When ``object_type`` is an
        observable, it is stored with the ``observable:`` prefix and stripped here.
        """
        return self.object_type.removeprefix('observable:')

    @computed_field
    @property
    def date(self) -> int:
        return self.startDate

    @computed_field
    @property
    def createdAt(self) -> int:
        return self.startDate

    @computed_field
    @property
    def updatedAt(self) -> int:
        return self.endDate

    @computed_field
    @property
    def type(self) -> str:
        return self.worker.type

    @computed_field
    @property
    def analyzerId(self) -> str:
        return self.worker.id

    @computed_field
    @property
    def analyzerName(self) -> str:
        return self.worker.name

    @computed_field
    @property
    def workerId(self) -> str:
        return self.worker.id

    @computed_field
    @property
    def workerName(self) -> str:
        return self.worker.name

    @computed_field
    @property
    def analyzerDefinitionId(self) -> str:
        return self.worker.id

    @computed_field
    @property
    def workerDefinitionId(self) -> str:
        return self.worker.id

    @computed_field
    @property
    def startDate(self) -> int:
        """Return start date in Cortex format."""
        return int(self.started.timestamp()*1000)

    @computed_field
    @property
    def endDate(self) -> int:
        """Return end date in Cortex format."""
        try:
            return int(self.ended.timestamp()*1000)
        except AttributeError:
            return

    @computed_field
    @property
    def report(self) -> dict:
        """
        Cortex-shaped report for TheHive.

        When the worker posted JSON to ``POST /api/job/{id}/callback``, that payload is returned
        once the job has finished (``Success`` or ``Failure``). If the payload omits ``success``,
        it is set from the Kubernetes job outcome (``True`` for ``Success``, ``False`` for
        ``Failure``). With no callback, success uses a minimal placeholder; failure points at the
        Kubernetes job id.
        """
        if self.kube_status in ('Waiting', 'InProgress'):
            return {}

        if self.kube_status in ('Success', 'Failure') and self.callback_report is not None:
            out = dict(self.callback_report)
            if 'success' not in out:
                out['success'] = self.kube_status == 'Success'
            return out

        if self.kube_status == 'Failure':
            return {
                'success': False,
                'errorMessage': f'Job failed; check the Kubernetes job {self.id}.',
            }
        if self.kube_status == 'Success':
            return {'success': True, 'full': {'message': NO_CALLBACK_REPORT_MESSAGE}}
        return {}
