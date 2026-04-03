import logging
import argparse
import sys
from os import environ
from requests import Session
from requests.exceptions import HTTPError
from urllib.parse import urljoin

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
    """Execute the job script with arguments passed from the runner."""
    try:
        # parse arguments
        parser = argparse.ArgumentParser(description='Run the job')
        parser.add_argument('--object-type', required=True)
        parser.add_argument('--object-id', required=True)
        parser.add_argument('--context-type', default=None, choices=['alert', 'case'])
        parser.add_argument('--context-id', default=None)
        args = parser.parse_args()

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

    except Exception as e:
        print(f'Unhandled exception: {e}')
        sys.exit(1)
