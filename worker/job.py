import argparse
import logging
import sys
from os import environ

import requests
from requests import RequestException, Session
from requests.exceptions import HTTPError
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


def post_cerebro_report(report: dict) -> None:
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


class ThehiveClient(Session):
    def __init__(self,
                 base_url = environ['TH_URL'],
                 key = environ.get('TH_KEY'),
                 user = environ.get('TH_USER'),
                 password = environ.get('TH_PASSWORD')
                ):
        super().__init__()
        self.base_url = base_url
        if key:
            self.headers = {
                'Authorization': f'Bearer {key}'
            }
        else:
            self.auth = (user, password)

    def request(self, method, url, *args, **kwargs):
        joined_url = urljoin(self.base_url, url)
        return super().request(method, joined_url, *args, **kwargs)

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        stream=sys.stderr,
    )
    try:
        # parse arguments
        parser = argparse.ArgumentParser(description='Run the job')
        parser.add_argument('--object-type', required=True)
        parser.add_argument('--object-id', required=True)
        parser.add_argument('--context-type', default=None, choices=['alert', 'case'])
        parser.add_argument('--context-id', default=None)
        args = parser.parse_args()

        logger.info(
            f'Worker starting object_type={args.object_type!r} object_id={args.object_id!r} '
            f'context_type={args.context_type!r} context_id={args.context_id!r}'
        )

        try:
            # initialize thehive client
            thehive = ThehiveClient()

        except KeyError as e:
            print(f'Missing configuration: {e}')
            sys.exit(1)

        try:
            # do something with thehive api
            if args.object_type == 'thehive:alert':
                r = thehive.get(f'/api/v1/alert/{args.object_id}')
                r.raise_for_status()
                print('Alert title:', r.json()['title'])

            if args.object_type == 'thehive:case':
                r = thehive.get(f'/api/v1/case/{args.object_id}')
                r.raise_for_status()
                print('Case title:', r.json()['title'])

            if args.object_type == 'thehive:case_artifact':
                r = thehive.get(f'/api/v1/{args.context_type}/{args.context_id}')
                r.raise_for_status()
                context = r.json()

                r = thehive.get(f'/api/v1/observable/{args.object_id}')
                r.raise_for_status()
                observable = r.json()

                print(f"Observable {observable['dataType']} from {args.context_type} {context['title']}")

        except HTTPError as e:
            print(f'Connection error: {e}')
            sys.exit(1)

        try:
            post_cerebro_report(
                {
                    'success': True,
                    'full': {'message': 'dummy report from worker'},
                }
            )
        except RequestException as e:
            logger.warning(f'Callback to Cerebro failed: {e}')

    except Exception as e:
        print(f'Unhandled exception: {e}')
        sys.exit(1)
