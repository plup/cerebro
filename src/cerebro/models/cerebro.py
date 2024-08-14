import logging
import yaml
import json
from os import environ
from uuid import uuid4
from datetime import datetime
from pydantic import (BaseModel, Field, computed_field, field_validator, ValidationError,
                      ConfigDict, PrivateAttr)
from fastapi import HTTPException
from kubernetes import client, config, utils

logger = logging.getLogger('uvicorn.error')


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
    def list(cls) -> list:
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
        return [w for w in cls.list() if not (type and w.type != type
                                              or trigger and trigger not in w.triggers)]

    @classmethod
    def get(cls, name):
        """Get a worker by name."""
        try:
            return next(w for w in cls.list() if w.name == name)
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
    def create(cls, worker_id, object_type, object_id, context_type=None, context_id=None):
        # get the worker model
        worker = Worker.get(worker_id)

        # extend the manifest definition
        try:
            manifest = worker.manifest
            # keep track of data expected by thehive
            manifest['metadata']['annotations'] = {
                    'cerebro/worker': worker_id,
                    'cerebro/type': object_type
                }

            # collect ids and type for the script exectuion
            args = ['--object-type', object_type, '--object-id', object_id]
            if context_type and context_id:
                args.extend(['--context-type', context_type, '--context-id', context_id])

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
            object_type = object_type,
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

                message = f'{job_id} last words: {logs.splitlines()[-1]}'

            except client.exceptions.ApiException as e:
                logger.warning(e)
                message = f'{job_id} logs not accessible'

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
