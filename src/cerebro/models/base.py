"""Core models for Cerebro.

This module holds everything required for the orchestrator to run cleanly: workers, Kubernetes
jobs, artefacts parsed from TheHive, and integration with the cluster API. It is intentionally
independent of Cortex-specific API shapes.
"""
import copy
import logging
import yaml
import json
from os import environ
from typing import Any
from uuid import uuid4
from datetime import datetime
from pydantic import (BaseModel, Field, computed_field, field_validator, ValidationError,
                      ConfigDict, PrivateAttr)
from kubernetes import client, config, utils

from cerebro.callback import get_stored_report

logger = logging.getLogger(__name__)


def inject_callback_env(manifest: dict) -> None:
    """Add env vars so the worker can POST a Cortex report back (optional, requires secret and URL)."""
    try:
        secret = environ['CEREBRO_CALLBACK_SECRET']
    except KeyError:
        return
    try:
        base = environ['CEREBRO_CALLBACK_URL'].rstrip('/')
    except KeyError:
        logger.warning(
            'CEREBRO_CALLBACK_SECRET is set but CEREBRO_CALLBACK_URL is missing; skipping callback env injection'
        )
        return
    container = manifest['spec']['template']['spec']['containers'][0]
    extra = [
        {'name': 'CEREBRO_CALLBACK_URL', 'value': base},
        {'name': 'CEREBRO_CALLBACK_TOKEN', 'value': secret},
        {
            'name': 'CEREBRO_JOB_ID',
            'valueFrom': {'fieldRef': {'fieldPath': "metadata.labels['job-name']"}},
        },
    ]
    env = container.setdefault('env', [])
    existing = {e['name'] for e in env if isinstance(e, dict) and 'name' in e}
    for item in extra:
        if item['name'] not in existing:
            env.append(item)


class WorkerNotFoundError(RuntimeError):
    """The requested worker hasn't been found."""

class WorkerConfigurationError(RuntimeError):
    """The requested worker can't be loaded."""

class JobExecutionError(RuntimeError):
    """The job failed to execute."""


class Worker(BaseModel):
    name: str
    type: str
    manifest: dict
    triggers: list[str]
    version: str = '1.0'
    description: str = ''

    @computed_field
    @property
    def id(self) -> str:
        """Bind name and id."""
        # this solves a bug from TheHive requesting anlyzer by id but providing a name
        return self.name

    @classmethod
    def _load(cls) -> list:
        """
        Return the worker config without validation.

        This is usefull for mocking in unit testing.
        """
        try:
            with open(environ['WORKER_CONFIG'], 'r') as f:
                return yaml.safe_load(f)
        except KeyError:
            logger.warning('WORKER_CONFIG path not set.')
            return []

    @classmethod
    def list_workers(cls) -> list:
        """Return a list of configured workers."""
        workers = []
        for item in cls._load():
            try:
                workers.append(cls(**item))

            except ValidationError as e:
                logger.error(f'Worker definition is incorrect: {e}')

        return workers

    @classmethod
    def search(cls, type=None, trigger=None) -> list:
        """Filter list of workers."""
        return [w for w in cls.list_workers() if not (type and w.type != type
                                              or trigger and trigger not in w.triggers)]

    @classmethod
    def get(cls, name):
        """Get a worker by name."""
        try:
            return next(w for w in cls.list_workers() if w.name == name)
        except StopIteration:
            raise WorkerNotFoundError()


class K8sJob(BaseModel):
    """Wrapper around a Kubernetes job execution."""
    id: str
    worker: Worker
    object_type: str
    status: str
    started: datetime
    ended: datetime | None = None
    message: str = ''
    callback_report: dict | None = Field(default=None, exclude=True)

    @staticmethod
    def load_kube_config():
        """
        Successively tries to load config from cluster or local config file and return the current
        namespace.
        """
        try:
            config.load_incluster_config()
            return open("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read()
        except config.config_exception.ConfigException:
            config.load_kube_config()
            contexts, active_context = config.list_kube_config_contexts()
            return active_context['context']['namespace']

    @classmethod
    def create(cls, worker_id, artefact):
        # get the worker model
        worker = Worker.get(worker_id)

        # extend the manifest definition
        try:
            manifest = copy.deepcopy(worker.manifest)
            try:
                manifest['spec']['template']['spec']['containers'][0]['image'] = environ[
                    'OVERRIDE_WORKER_IMAGE'
                ]
            except KeyError:
                pass
            # keep track of data expected by thehive
            manifest['metadata']['annotations'] = {
                    'cerebro/worker': worker_id,
                    'cerebro/type': artefact.type,
                    'cerebro/id': artefact.id,
                    'cerebro/invocation-type': worker.type,
                }

            inject_callback_env(manifest)

            container = manifest['spec']['template']['spec']['containers'][0]
            env = container.setdefault('env', [])
            existing = {e['name'] for e in env if isinstance(e, dict) and 'name' in e}
            if 'CEREBRO_INVOCATION_TYPE' not in existing:
                env.append({'name': 'CEREBRO_INVOCATION_TYPE', 'value': worker.type})

            # collect ids and type for the script exectuion
            args = [
                '--invocation-type',
                worker.type,
                '--object-type',
                artefact.type,
                '--object-id',
                artefact.id,
            ]
            if artefact.ctx_type and artefact.ctx_id:
                args.extend(['--context-type', artefact.ctx_type, '--context-id', artefact.ctx_id])

            # pass the args to the job entrypoint
            try:
                manifest['spec']['template']['spec']['containers'][0]['args'].extend(args)
            except KeyError:
                manifest['spec']['template']['spec']['containers'][0]['args'] = args

            logger.info(f'Launching a job instance of {worker.name} with {" ".join(args)}')

        except KeyError as e:
            logger.error(f'{e} not define in manifest')
            raise WorkerConfigurationError(f'The k8s manifest is not define properly')

        # create the job
        try:
            namespace = cls.load_kube_config()
            k8s_job = utils.create_from_dict(client.ApiClient(), manifest, namespace=namespace)[0]
            logger.info(f'Creating {k8s_job.metadata.name}')
        except client.exceptions.ApiException as e:
            logger.error(e)
            raise JobExecutionError('Failed to create the kube job')

        return cls(
            id = k8s_job.metadata.name,
            worker = worker,
            object_type = artefact.type,
            status = 'Waiting',
            started = k8s_job.metadata.creation_timestamp,
            callback_report = None,
        )

    @classmethod
    def fetch(cls, job_id):
        # read the job from kube
        try:
            namespace = cls.load_kube_config()
            k8s_job = client.BatchV1Api().read_namespaced_job(name=job_id, namespace=namespace)

        except client.exceptions.ApiException as e:
            logger.error(e)
            raise JobExecutionError(f"Can't access job {job_id} in kube")

        # retreive worker parameters
        try:
            worker = Worker.get(k8s_job.metadata.annotations['cerebro/worker'])
            object_type = k8s_job.metadata.annotations['cerebro/type']

        except KeyError as e:
            logger.error(e)
            raise JobExecutionError("Can't retreive worker config from the job's annotations")

        if k8s_job.status.active:
            # nothing to return if the job is still executing
            status = 'InProgress'
            message = ''

        else:
            # map result conditions
            if k8s_job.status.failed and k8s_job.status.failed > 0:
                status = 'Failure'
            else:
                status = 'Success'

            message = ''

        return cls(
            id = job_id,
            worker = worker,
            object_type = object_type,
            status = status,
            started = k8s_job.metadata.creation_timestamp,
            ended = k8s_job.status.completion_time,
            message = message,
            callback_report = get_stored_report(job_id),
        )

class ThehiveArtefact(BaseModel):
    """
    Normalized target for a Cerebro job (Kubernetes worker args).

    Cortex **analyzer** runs use :meth:`from_analyzer_event` (flat observable: ``dataType`` +
    ``data``). **Responder** runs use :meth:`from_responder_event` (nested ``thehive:*`` objects).
    """
    type: str
    id: str
    ctx_type: str = ''
    ctx_id: str = ''

    @classmethod
    def from_responder_event(cls, event: Any) -> 'ThehiveArtefact':
        """Build from ``POST /api/responder/.../run`` bodies (nested TheHive object references)."""
        try:
            artefact: dict[str, str] = {}
            dt = event['dataType']
            # Nested payloads (TheHive object references)
            if dt == 'thehive:case_artifact':
                artefact['type'] = 'observable:' + event['data']['dataType']
                artefact['id'] = event['data']['id']
                try:
                    artefact['ctx_id'] = event['data']['alert']['id']
                    artefact['ctx_type'] = 'alert'

                except KeyError:
                    artefact['ctx_id'] = event['data']['case']['id']
                    artefact['ctx_type'] = 'case'

            elif dt == 'thehive:alert':
                artefact['type'] = 'alert'
                artefact['id'] = event['data']['id']

            elif dt == 'thehive:case':
                artefact['type'] = 'case'
                artefact['id'] = event['data']['id']

            else:
                raise ValueError(f'Responder payload: unsupported dataType {dt!r}')

            return cls.model_validate(artefact)

        except KeyError as e:
            logger.error(f"Payload malformed, missing {e}")
            raise ValueError("Payload malformed")

    @classmethod
    def from_analyzer_event(cls, event: Any) -> 'ThehiveArtefact':
        """Build from ``POST /api/analyzer/.../run`` bodies (flat Cortex analyzer run)."""
        try:
            dt = event['dataType']
            if str(dt).startswith('thehive:'):
                raise ValueError(
                    f'Analyzer runs expect a flat observable (dataType + data); got {dt!r}'
                )

            artefact: dict[str, str] = {}
            artefact['type'] = f'observable:{dt}'
            data_val = event.get('data')
            if isinstance(data_val, str) and data_val != '':
                oid = event.get('id') or event.get('artifactId')
                artefact['id'] = oid if oid is not None else data_val
            elif isinstance(event.get('attachment'), dict):
                att = event['attachment']
                aid = att.get('id')
                if aid is None:
                    raise ValueError('Payload malformed: attachment needs id')
                oid = event.get('id') or event.get('artifactId')
                artefact['id'] = oid if oid is not None else str(aid)
            else:
                raise ValueError('Payload malformed: analyzer run needs string data or attachment id')

            msg = event.get('message')
            if msg is not None and str(msg) != '':
                artefact['ctx_type'] = 'case'
                artefact['ctx_id'] = str(msg)

            return cls.model_validate(artefact)

        except KeyError as e:
            logger.error(f"Payload malformed, missing {e}")
            raise ValueError("Payload malformed")
