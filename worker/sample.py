import logging
import sys

from neuron import CerebroNeuron

if __name__ == '__main__':

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        stream=sys.stderr,
    )

    try:
        neuron = CerebroNeuron()
        logging.info(neuron.args)

        if neuron.args.invocation_type == 'responder':
            # Responders run on any types of entities and get access to a context so we 
            # can track back an observable in an alert or case
            obj_type = neuron.args.object_type
            obj_id = neuron.args.object_id

            report = {
                'full': {
                    # in responder context the report needs to be short
                    "message": "Execution went well!"
                },
                'operations': [
                    # operations require to identify with which entity
                    # we are working with
                ],
            }

        if neuron.args.invocation_type == 'analyzer':
            # Analyzers run on observable and can only access the obervable type and value
            # no context whatsoever
            obs_type = neuron.args.object_type
            obs_value = neuron.args.object_value

            report = {
                'summary': {
                    'taxonomies': [
                        {
                            'namespace': 'Example',
                            'predicate': obs_type,
                            'value': obs_value,
                            'level': 'info',
                        },
                    ],
                },
                'full': {
                    'query': 'anything',
                    'details': {
                        'first_seen': '2025-01-15T10:00:00Z',
                    },
                },
                'operations': [
                    {
                        'type': 'AddTagToArtifact',
                        'tag': 'analyzed',
                    },
                ],
                'artifacts': [
                    # this needs to map an analyzer obserable in TheHive schema
                    {
                        'data': obs_value,
                        'dataType': obs_type.removeprefix('observable:'),
                        'message': None,
                        'tags': ['example'],
                        'tlp': 2,
                    },
                ],
            }

        try:
            neuron.send_report(report)

        except RequestException as exc:
            logger.warning(f'Callback to Cerebro failed: {exc}')

    except Exception as e:
        logging.exception(f'Unhandled exception: {e}')
        raise SystemExit()
