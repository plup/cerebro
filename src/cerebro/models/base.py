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
from pathlib import Path
from typing import Any
from uuid import uuid4
from datetime import datetime
from pydantic import (BaseModel, Field, computed_field, field_validator, ValidationError,
                      ConfigDict, PrivateAttr)
from kubernetes import client, config, utils

from cerebro.callback import get_stored_report

logger = logging.getLogger(__name__)

# When ``WORKER_CONFIG`` is unset, load worker YAML from this path (matches the k8s Deployment).
DEFAULT_WORKER_CONFIG_PATH = '/etc/cerebro/workers'


def read_worker_config() -> list[dict[str, Any]]:
    f"""
    Read worker definitions from disk as plain dicts (before Pydantic validation).

    Uses the ``WORKER_CONFIG`` environment variable; if unset, the path defaults to
    ``{DEFAULT_WORKER_CONFIG_PATH}``. The path may be either a **file** or a **directory**.
    A file contains one YAML mapping (one worker). A directory loads every ``*.yml`` and
    ``*.yaml`` in sorted filename order, one mapping per file. Mount several ConfigMaps into
    the same directory (for example with a projected volume) to ship one worker per ConfigMap.

    Returns a list of dicts, or an empty list when nothing could be loaded; issues are logged
    at warning or error level.
    """
    path = Path(environ.get('WORKER_CONFIG', DEFAULT_WORKER_CONFIG_PATH))

    if not path.exists():
        logger.warning(f'WORKER_CONFIG path does not exist: {path}')
        return []

    if path.is_dir():
        merged: list[dict[str, Any]] = []
        worker_files = sorted(
            (*path.glob('*.yml'), *path.glob('*.yaml')),
            key=lambda p: p.name,
        )
        for file_path in worker_files:
            try:
                with open(file_path, encoding='utf-8') as fh:
                    raw = yaml.safe_load(fh)
            except OSError as e:
                logger.error(f'Could not read worker file {file_path}: {e}')
                continue
            except yaml.YAMLError as e:
                logger.error(f'Invalid YAML in worker file {file_path}: {e}')
                continue
            if not isinstance(raw, dict):
                got = type(raw).__name__
                logger.error(
                    f'Worker file {file_path} must contain a YAML mapping; got {got}'
                )
                continue
            merged.append(raw)
        return merged

    try:
        with open(path, encoding='utf-8') as f:
            raw = yaml.safe_load(f)
    except OSError as e:
        logger.error(f'Could not read WORKER_CONFIG {path}: {e}')
        return []
    except yaml.YAMLError as e:
        logger.error(f'Invalid YAML in WORKER_CONFIG {path}: {e}')
        return []

    if not isinstance(raw, dict):
        got = type(raw).__name__
        logger.error(f'WORKER_CONFIG {path} must contain a YAML mapping; got {got}')
        return []
    return [raw]


def inject_callback_env(manifest: dict) -> None:
    """Add env vars so the worker can POST a Cortex report back (optional; needs URL and API key)."""
    try:
        api_key = environ['CEREBRO_API_KEY']
    except KeyError:
        return
    try:
        base = environ['CEREBRO_CALLBACK_URL'].rstrip('/')
    except KeyError:
        logger.warning(
            'CEREBRO_API_KEY is set but CEREBRO_CALLBACK_URL is missing; skipping callback env injection'
        )
        return
    container = manifest['spec']['template']['spec']['containers'][0]
    extra = [
        {'name': 'CEREBRO_CALLBACK_URL', 'value': base},
        {'name': 'CEREBRO_CALLBACK_TOKEN', 'value': api_key},
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


THEHIVE_WORKER_ENV_NAMES = ('TH_URL', 'TH_KEY', 'TH_USER', 'TH_PASSWORD')


def inject_cerebro_invocation_env(manifest: dict, artefact: Any) -> None:
    """
    Pass analyzer/responder invocation fields to the worker container via environment variables.

    Keeps container ``args`` free for image-specific or manifest-defined flags.
    """
    updates = {
        'CEREBRO_OBJECT_TYPE': artefact.type,
        'CEREBRO_OBJECT_VALUE': artefact.data,
        'CEREBRO_OBJECT_ID': artefact.id,
        'CEREBRO_CONTEXT_TYPE': artefact.ctx_type or '',
        'CEREBRO_CONTEXT_ID': artefact.ctx_id or '',
    }
    container = manifest['spec']['template']['spec']['containers'][0]
    env = container.setdefault('env', [])
    env[:] = [e for e in env if not (isinstance(e, dict) and e.get('name') in updates)]
    env.extend({'name': k, 'value': v} for k, v in updates.items())


def inject_thehive_env(manifest: dict) -> None:
    """
    Apply TheHive settings from the Cerebro process environment to the worker container.

    For each name present in ``os.environ``, the worker manifest is updated or extended so all
    workers receive the same TheHive connection configuration as the Cerebro deployment.
    Names not set in the orchestrator are left unchanged (any values from the worker manifest
    stay in place).
    """
    container = manifest['spec']['template']['spec']['containers'][0]
    env = container.setdefault('env', [])
    index_by_name: dict[str, int] = {}
    for i, entry in enumerate(env):
        if isinstance(entry, dict) and 'name' in entry:
            index_by_name[entry['name']] = i
    for name in THEHIVE_WORKER_ENV_NAMES:
        try:
            value = environ[name]
        except KeyError:
            continue
        pair = {'name': name, 'value': value}
        if name in index_by_name:
            env[index_by_name[name]] = pair
        else:
            env.append(pair)
            index_by_name[name] = len(env) - 1


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
    def list_workers(cls) -> list:
        """Return a list of configured workers."""
        workers = []
        for item in read_worker_config():
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
    kube_status: str
    started: datetime
    ended: datetime | None = None
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
            inject_thehive_env(manifest)

            container = manifest['spec']['template']['spec']['containers'][0]
            env = container.setdefault('env', [])
            existing = {e['name'] for e in env if isinstance(e, dict) and 'name' in e}
            if 'CEREBRO_INVOCATION_TYPE' not in existing:
                env.append({'name': 'CEREBRO_INVOCATION_TYPE', 'value': worker.type})

            inject_cerebro_invocation_env(manifest, artefact)

            logger.info(
                f'Launching job {worker.name} worker.type={worker.type} object_type={artefact.type}'
            )

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
            kube_status = 'Waiting',
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
            kube_status = 'InProgress'
        else:
            # map result conditions
            if k8s_job.status.failed and k8s_job.status.failed > 0:
                kube_status = 'Failure'
            else:
                kube_status = 'Success'

        return cls(
            id = job_id,
            worker = worker,
            object_type = object_type,
            kube_status = kube_status,
            started = k8s_job.metadata.creation_timestamp,
            ended = k8s_job.status.completion_time,
            callback_report = get_stored_report(job_id),
        )

class ThehiveArtefact(BaseModel):
    """
    Normalized target for a Cerebro job (Kubernetes worker environment variables).

    Observable targets always use the ``observable:`` prefix (e.g. ``observable:hostname``) so they
    are distinct from ``case`` and ``alert``. **Analyzer** runs use :meth:`from_analyzer_event`
    (flat ``dataType`` + ``data`` in the request, stored as ``observable:`` + ``dataType``).
    **Responders** use :meth:`from_responder_event` (nested ``thehive:*`` objects).

    For analyzers, ``data`` is always the raw observable value from the request (the ``data``
    field). ``id`` is only set from TheHive ``id`` or ``artifactId`` when present; it is never
    copied from ``data``. Analyzer runs do not populate ``ctx_type`` / ``ctx_id`` (the ``message``
    field is not a reliable case or alert reference).
    """
    type: str
    id: str
    data: str = ''
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
                artefact['id'] = str(oid) if oid is not None else ''
                artefact['data'] = data_val
            elif isinstance(event.get('attachment'), dict):
                att = event['attachment']
                aid = att.get('id')
                if aid is None:
                    raise ValueError('Payload malformed: attachment needs id')
                oid = event.get('id') or event.get('artifactId')
                artefact['id'] = str(oid) if oid is not None else ''
                raw = event.get('data')
                if isinstance(raw, str) and raw != '':
                    artefact['data'] = raw
                else:
                    artefact['data'] = str(att.get('name') or att.get('filename') or aid)
            else:
                raise ValueError('Payload malformed: analyzer run needs string data or attachment id')

            # Do not map ``message`` to context: TheHive may send free-form strings there (e.g.
            # alert fingerprints) that are not a case/alert id. Analyzers have no responder-style
            # context; ``ctx_type`` / ``ctx_id`` stay unset.

            return cls.model_validate(artefact)

        except KeyError as e:
            logger.error(f"Payload malformed, missing {e}")
            raise ValueError("Payload malformed")
