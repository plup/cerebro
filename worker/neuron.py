"""Cerebro worker: invocation env, Cortex-shaped reports, and callback to the orchestrator."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from os import environ
from typing import Any

import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InvocationParams:
    """Invocation target for a worker run (from Cerebro-injected ``CEREBRO_*`` environment variables)."""

    role: str
    object_type: str
    object_value: str | None
    object_id: str | None
    context_type: str | None
    context_id: str | None

    @classmethod
    def from_environ(cls) -> InvocationParams:
        """Read and validate invocation fields from the process environment."""
        try:
            role = environ['CEREBRO_INVOCATION_TYPE']
        except KeyError as e:
            raise ValueError('CEREBRO_INVOCATION_TYPE is required') from e
        if role not in ('analyzer', 'responder'):
            raise ValueError('CEREBRO_INVOCATION_TYPE must be analyzer or responder')

        object_type = environ.get('CEREBRO_OBJECT_TYPE') or None
        object_value = environ.get('CEREBRO_OBJECT_VALUE') or None
        object_id = environ.get('CEREBRO_OBJECT_ID') or None
        raw_ctx_t = environ.get('CEREBRO_CONTEXT_TYPE', '')
        raw_ctx_i = environ.get('CEREBRO_CONTEXT_ID', '')
        context_type = raw_ctx_t if raw_ctx_t in ('alert', 'case') else None
        context_id = raw_ctx_i or None

        if role == 'analyzer':
            if object_type is None or object_value is None:
                raise ValueError(
                    'analyzer runs require CEREBRO_OBJECT_TYPE and CEREBRO_OBJECT_VALUE'
                )
        else:
            if object_type is None or object_id is None:
                raise ValueError(
                    'responder runs require CEREBRO_OBJECT_TYPE and CEREBRO_OBJECT_ID'
                )

        return cls(
            role=role,
            object_type=object_type,
            object_value=object_value,
            object_id=object_id,
            context_type=context_type,
            context_id=context_id,
        )


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

    def get_observable(self, observable_id: str) -> dict[str, Any]:
        """
        Fetch a single observable by id (TheHive 5+ ``GET /api/v1/observable/{id}``).
        """
        r = self.get(f'/api/v1/observable/{observable_id}')
        r.raise_for_status()
        return r.json()


class CerebroNeuron:
    """
    Loads invocation from environment variables, initializes a TheHive client, builds the Cortex
    ``report`` JSON, and POSTs it to Cerebro.
    """

    def __init__(self):
        self.invocation = InvocationParams.from_environ()
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

    def send_report(self, report: dict) -> None:
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
        inv = self.invocation
        if inv.role == 'analyzer':
            logger.info(
                f'Worker starting role={inv.role!r} '
                f'object_type={inv.object_type!r} object_value={inv.object_value!r}'
            )
        else:
            logger.info(
                f'Worker starting role={inv.role!r} '
                f'object_type={inv.object_type!r} object_id={inv.object_id!r} '
                f'context_type={inv.context_type!r} context_id={inv.context_id!r}'
            )
