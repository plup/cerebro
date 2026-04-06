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
                      ConfigDict, PrivateAttr, model_validator)
from fastapi import HTTPException
from kubernetes import client, config, utils

logger = logging.getLogger(__name__)


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
                }

            # collect ids and type for the script exectuion
            args = ['--object-type', artefact.type, '--object-id', artefact.id]
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

            # format a message from the logs
            try:
                # get the related pod
                uid = k8s_job.metadata.uid
                pod = client.CoreV1Api().list_namespaced_pod(
                        namespace = namespace,
                        label_selector = f'batch.kubernetes.io/controller-uid={uid}',
                        timeout_seconds = 10
                    ).items[0]

                # get the pod logs
                logs = client.CoreV1Api().read_namespaced_pod_log(
                        name = pod.metadata.name,
                        namespace = namespace,
                        _return_http_data_only = True,
                        _preload_content = False
                    ).data.decode()

                message = f'{job_id}: {logs.splitlines()[-1]}'

            except client.exceptions.ApiException as e:
                logger.warning(e)
                message = f'{job_id} logs are not accessible'

            except IndexError:
                message = f'{job_id} didn\'t log anything'

        return cls(
            id = job_id,
            worker = worker,
            object_type = object_type,
            status = status,
            started = k8s_job.metadata.creation_timestamp,
            ended = k8s_job.status.completion_time,
            message = message,
        )

class ThehiveArtefact(BaseModel):
    type: str
    id: str
    ctx_type: str = ''
    ctx_id: str = ''

    @model_validator(mode='before')
    @classmethod
    def parse(cls, event: Any) -> Any:
        """
        Parse event and return a simplified object representing the artefact sent by TheHive.

        This is an attempt to unify the analyzers and responders inputs by flattening them.
        It only keeps track of the object types and ids leaving to the job the charge to make
        a request to get the details.
        It also keeps the alert or case id for observables because TheHive doesn't provide a way
        to get them from the observable itself.
        """
        try:
            artefact: dict[str, str] = {}
            dt = event['dataType']
            # Responder-style nested payloads (TheHive object references)
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

            elif not str(dt).startswith('thehive:'):
                # Flat Cortex analyzer run body: dataType is the observable type (e.g. hostname,
                # domain), data is the value string; optional message often carries case context.
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

            else:
                raise ValueError(f'Payload malformed: unsupported dataType {dt!r}')

            if not artefact:
                raise ValueError('Payload malformed: empty artefact')

            return artefact

        except KeyError as e:
            logger.error(f"Payload malformed, missing {e}")
            raise ValueError("Payload malformed")
