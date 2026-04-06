"""Cortex-compatible façade over ``cerebro.models.base``.

Cerebro is an in-place replacement for Cortex. The base model layer contains all and only what
Cerebro needs to operate; this module extends those types so responses and job objects match what
Cortex exposes (e.g. analyzers, responders, and ``CortexJob`` for TheHive).
"""
from pydantic import Field, computed_field, field_validator
from .base import Worker, K8sJob

# Shown in ``report`` when the job finished without a callback payload (Cortex-compatible text).
NO_CALLBACK_REPORT_MESSAGE = 'No report has been generated.'


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
    """
    worker: Worker = Field(exclude=True)
    organization: str = '' # Cortex normally returns organization but it's apparently not checked by TheHive

    @computed_field
    @property
    def dataType(self) -> str:
        """Cortex-facing datatype (internal ``object_type`` uses ``observable:`` for analyzers)."""
        ot = self.object_type
        if self.worker.type == 'analyzer' and ot.startswith('observable:'):
            return ot.removeprefix('observable:')
        return ot

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
        Generate a report for TheHive.

        If the worker posted a JSON body to ``POST /api/job/{id}/callback``, that dict is used
        once the job has finished (Success or Failure). Otherwise a placeholder message is used
        (pod logs are not surfaced here).
        """
        if self.callback_report is not None and self.status in ('Success', 'Failure'):
            return self.callback_report
        if self.status == 'Failure':
            return {'success': False, 'errorMessage': NO_CALLBACK_REPORT_MESSAGE}
        elif self.status == 'Success':
            return {'success': True, 'full': {'message': NO_CALLBACK_REPORT_MESSAGE}}
        else:
            return {}
