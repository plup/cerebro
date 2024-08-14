import logging
import argparse
import sys
from os import environ
from thehive4py import TheHiveApi

logging.basicConfig(format=None)

if __name__ == '__main__':
    """Execute the job script with arguments passed from the runner."""
    try:
        # parse arguments
        parser = argparse.ArgumentParser(description='Run the test job')
        parser.add_argument('--object-type', required=True)
        parser.add_argument('--object-id', required=True)
        parser.add_argument('--context-type', default=None, choices=['alert', 'case'])
        parser.add_argument('--context-id', default=None)
        args = parser.parse_args()
        if args.object_type != 'thehive:case_artifact':
            raise NotImplementedError(f'The object type {args.object_type} is not supported by this job')

        # initialize thehive client
        hive = TheHiveApi(url=environ['TH_URL'], apikey=environ['TH_KEY'])

        # do something with thehive api
        print(hive.observable.get(args.object_id))

    except KeyError as e:
        logging.critical(f'Environment missing: {e}')
        sys.exit(1)

    except Exception as e:
        logging.critical(str(e))
        sys.exit(1)
