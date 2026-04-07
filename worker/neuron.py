"""Cerebro worker: CLI, Cortex-shaped reports, and callback to the orchestrator."""
from __future__ import annotations

import argparse
import logging
import sys
from argparse import Namespace
from os import environ

import requests
from requests import RequestException
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


def echo_cortex_data_type_and_data(object_type: str, object_id: str) -> tuple[str, str]:
    if object_type.startswith('observable:'):
        return object_type.removeprefix('observable:'), object_id
    return object_type, object_id


def observable_type_suffix(object_type: str) -> str:
    """Cortex datatype without ``observable:`` (e.g. ``observable:ip`` → ``ip``)."""
    if object_type.startswith('observable:'):
        return object_type.removeprefix('observable:')
    return object_type


class ThehiveClient(requests.Session):
    """HTTP session for TheHive (``TH_URL``, ``TH_KEY`` or ``TH_USER`` / ``TH_PASSWORD``)."""

    def __init__(
        self,
        base_url: str | None = None,
        key: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        super().__init__()
        self.base_url = base_url if base_url is not None else environ['TH_URL']
        if key is None:
            key = environ.get('TH_KEY')
        if user is None:
            user = environ.get('TH_USER')
        if password is None:
            password = environ.get('TH_PASSWORD')
        if key:
            self.headers = {'Authorization': f'Bearer {key}'}
        else:
            self.auth = (user, password)

    def request(self, method, url, *args, **kwargs):
        joined_url = urljoin(self.base_url, url)
        return super().request(method, joined_url, *args, **kwargs)


class CerebroNeuron:
    """
    Parses worker CLI args, initializes a TheHive client, builds the Cortex ``report`` JSON,
    and POSTs it to Cerebro.
    """

    def __init__(self, argv: list[str] | None = None):
        self.argv = argv if argv is not None else sys.argv[1:]
        self.args = self.parse_args(self.argv)
        self.thehive = self.build_thehive_client()

    def build_thehive_client(self) -> ThehiveClient | None:
        """Return a :class:`ThehiveClient` when ``TH_URL`` is set; otherwise ``None``."""
        try:
            client = ThehiveClient()
            logger.info(f'TheHive client initialized for {client.base_url!r}')
            return client
        except KeyError:
            logger.warning('TheHive client not initialized: TH_URL is not set')
            return None

    def parse_args(self, argv: list[str]) -> Namespace:
        parser = argparse.ArgumentParser(description='Run the job')
        parser.add_argument(
            '--invocation-type',
            required=True,
            choices=['analyzer', 'responder'],
            help='Cortex role for this run (analyzer vs responder), from the worker definition.',
        )
        parser.add_argument(
            '--object-type',
            help=(
                'Observable targets use the observable: prefix (e.g. observable:hostname). '
                'Responders may also use alert or case.'
            ),
        )
        parser.add_argument(
            '--object-value',
            dest='object_value',
            help='Observable value for analyzer runs (the analyzed string).',
        )
        parser.add_argument('--object-id', help='Target entity id for responder runs.')
        parser.add_argument('--context-type', default=None, choices=['alert', 'case'])
        parser.add_argument('--context-id', default=None)
        ns = parser.parse_args(argv)
        if ns.invocation_type == 'analyzer':
            if ns.object_type is None or ns.object_value is None:
                parser.error('analyzer runs require --object-type and --object-value')
        elif ns.object_type is None or ns.object_id is None:
            parser.error('responder runs require --object-type and --object-id')
        return ns

    def build_report(self) -> dict:
        if self.args.invocation_type == 'analyzer':
            return self.build_analyzer_report()
        return self.build_responder_report()

    def build_analyzer_report(self) -> dict:
        object_type = self.args.object_type
        object_value = self.args.object_value
        dt_suffix = observable_type_suffix(object_type)
        artifact_data = object_value if dt_suffix == 'ip' else '192.0.2.10'
        return {
            'success': True,
            'summary': {
                'taxonomies': [
                    {
                        'namespace': 'Example',
                        'predicate': object_type,
                        'value': 'found',
                        'level': 'info',
                    },
                ],
            },
            'full': {
                'query': object_value,
                'verdict': 'suspicious',
                'details': {
                    'first_seen': '2025-01-15T10:00:00Z',
                },
            },
            'operations': [
                {
                    'type': 'AddTagToCase',
                    'tag': 'From Action Operation',
                },
                {
                    'type': 'CreateTask',
                    'title': 'task created by action',
                    'description': 'yop !',
                },
            ],
            'artifacts': [
                {
                    'data': artifact_data,
                    'dataType': 'ip',
                    'message': None,
                    'tags': ['example'],
                    'tlp': 2,
                },
            ],
        }

    def build_responder_report(self) -> dict:
        data_type, data = echo_cortex_data_type_and_data(self.args.object_type, self.args.object_id)
        return {
            'success': True,
            'full': {
                'data_type': data_type,
                'data': data,
                'message': f'Echo: received {data_type}',
            },
            'operations': [
                {
                    'type': 'AddTagToCase',
                    'tag': 'From Action Operation',
                },
                {
                    'type': 'CreateTask',
                    'title': 'task created by action',
                    'description': 'yop !',
                },
            ],
        }

    def post_callback(self, report: dict) -> None:
        """
        POST a Cortex-shaped report to Cerebro (no-op unless callback env vars are injected).

        Requires ``CEREBRO_CALLBACK_URL``, ``CEREBRO_CALLBACK_TOKEN``, and ``CEREBRO_JOB_ID``.
        """
        base = environ.get('CEREBRO_CALLBACK_URL')
        token = environ.get('CEREBRO_CALLBACK_TOKEN')
        job_id = environ.get('CEREBRO_JOB_ID')
        if not all([base, token, job_id]):
            logger.info(
                'Skipping Cerebro callback: set CEREBRO_CALLBACK_URL, CEREBRO_CALLBACK_TOKEN, '
                'and CEREBRO_JOB_ID to post results'
            )
            return
        url = f"{base.rstrip('/')}/api/job/{job_id}/callback"
        logger.info(f'Posting report to Cerebro callback {url}')
        r = requests.post(
            url,
            json=report,
            headers={'Authorization': f'Bearer {token}'},
            timeout=120,
        )
        r.raise_for_status()
        logger.info(f'Cerebro callback accepted (HTTP {r.status_code})')

    def run(self) -> None:
        if self.args.invocation_type == 'analyzer':
            logger.info(
                f'Worker starting invocation_type={self.args.invocation_type!r} '
                f'object_type={self.args.object_type!r} object_value={self.args.object_value!r}'
            )
        else:
            logger.info(
                f'Worker starting invocation_type={self.args.invocation_type!r} '
                f'object_type={self.args.object_type!r} object_id={self.args.object_id!r} '
                f'context_type={self.args.context_type!r} context_id={self.args.context_id!r}'
            )
        try:
            self.post_callback(self.build_report())
        except RequestException as exc:
            logger.warning(f'Callback to Cerebro failed: {exc}')
