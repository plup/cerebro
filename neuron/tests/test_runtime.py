"""Neuron runtime failure callback tests."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from neuron.report import Report
from neuron.runtime import CerebroNeuron


class CerebroNeuronFailTest(unittest.TestCase):
    def test_send_report_adds_job_id_to_success(self) -> None:
        requests: list[dict] = []

        def post(url: str, **kwargs) -> httpx.Response:
            requests.append({'url': url, **kwargs})
            return httpx.Response(200, request=httpx.Request('POST', url))

        env = {
            'CEREBRO_INVOCATION_TYPE': 'analyzer',
            'CEREBRO_WORKER_NAME': 'worker',
            'CEREBRO_OBJECT_TYPE': 'observable:hostname',
            'CEREBRO_OBJECT_VALUE': 'host1',
            'CEREBRO_CALLBACK_URL': 'http://cerebro',
            'CEREBRO_CALLBACK_TOKEN': 'secret',
            'CEREBRO_JOB_ID': 'neuron-job-ok',
        }
        with patch.dict('os.environ', env, clear=True), patch(
            'neuron.runtime.httpx.post',
            side_effect=post,
        ):
            CerebroNeuron().send_report(Report().set_details({'message': 'done'}))

        self.assertEqual(
            requests[0]['json'],
            {
                'success': True,
                'full': {'message': 'done', 'jobId': 'neuron-job-ok'},
                'operations': [],
            },
        )

    def test_fail_posts_job_log_message(self) -> None:
        requests: list[dict] = []

        def post(url: str, **kwargs) -> httpx.Response:
            requests.append({'url': url, **kwargs})
            return httpx.Response(200, request=httpx.Request('POST', url))

        env = {
            'CEREBRO_INVOCATION_TYPE': 'analyzer',
            'CEREBRO_WORKER_NAME': 'worker',
            'CEREBRO_OBJECT_TYPE': 'observable:hostname',
            'CEREBRO_OBJECT_VALUE': 'host1',
            'CEREBRO_CALLBACK_URL': 'http://cerebro',
            'CEREBRO_CALLBACK_TOKEN': 'secret',
            'CEREBRO_JOB_ID': 'neuron-job-abc',
        }
        with patch.dict('os.environ', env, clear=True), patch(
            'neuron.runtime.httpx.post',
            side_effect=post,
        ):
            with self.assertRaises(SystemExit) as raised:
                CerebroNeuron().fail('implementation detail')

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(
            requests,
            [
                {
                    'url': 'http://cerebro/api/job/neuron-job-abc/callback',
                    'json': {
                        'success': False,
                        'errorMessage': 'Job neuron-job-abc failed: implementation detail',
                        'operations': [],
                    },
                    'headers': {'Authorization': 'Bearer secret'},
                    'timeout': 120.0,
                }
            ],
        )
