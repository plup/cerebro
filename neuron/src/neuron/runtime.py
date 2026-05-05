"""Cerebro neuron: invocation env, Cortex-shaped reports, and callback to the orchestrator."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from os import environ
from typing import Any, NoReturn

import httpx

from neuron.report import Report
from neuron.thehive import ThehiveClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InvocationParams:
    """Invocation target for a neuron run (from Cerebro-injected ``CEREBRO_*`` environment variables)."""

    role: str
    worker_name: str
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
        try:
            worker_name = environ['CEREBRO_WORKER_NAME']
        except KeyError as e:
            raise ValueError('CEREBRO_WORKER_NAME is required') from e
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
            worker_name=worker_name,
            object_type=object_type,
            object_value=object_value,
            object_id=object_id,
            context_type=context_type,
            context_id=context_id,
        )


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
            client = ThehiveClient(verify=bool(int(environ.get('TH_VERIFY', '1'))))
            logger.info(f'TheHive client initialized for {client.base_url!r}')
            return client
        except KeyError:
            logger.warning('TheHive client not initialized: TH_URL is not set')
            return None

    def send_report(self, report: Report) -> None:
        """
        POST a Cortex-shaped report to Cerebro (no-op unless callback env vars are injected).

        Requires ``CEREBRO_CALLBACK_URL``, ``CEREBRO_CALLBACK_TOKEN`` (same value as Cerebro's
        ``CEREBRO_API_KEY``), and ``CEREBRO_JOB_ID``.
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
        r = httpx.post(
            url,
            json=report.to_dict(),
            headers={'Authorization': f'Bearer {token}'},
            timeout=120.0,
        )
        r.raise_for_status()
        logger.info(f'Cerebro callback accepted (HTTP {r.status_code})')

    def fail(self, message: str) -> NoReturn:
        """
        Record a failed run (``success: false`` and ``errorMessage``), POST it to Cerebro when
        callback env vars are set, then exit the process with code 0 so the Job completes
        successfully while TheHive still sees a failed Cortex report.
        """
        logger.error(f'Neuron failed: {message}')
        self.send_report(Report(error_message=message))
        raise SystemExit(0)
