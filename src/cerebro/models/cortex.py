"""Define models specific to Cortex."""
from pydantic import BaseModel, Field, computed_field, field_validator
from .cerebro import Worker, K8sJob


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
        """Rename the object type."""
        return self.object_type

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

        Responders can't display long result so we limit the output to a simple message.
        "success: <true|false>" is returned by Cortex but seems to be ignored by TheHive.
        """
        if self.status == 'Failure':
            return {'success': False, 'errorMessage': self.message}
        elif self.status == 'Success':
            return {'success': True, 'full': {'message': self.message}}
        else:
            return {}
