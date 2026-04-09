import logging
import sys

from requests import RequestException

from neuron import CerebroNeuron

if __name__ == '__main__':

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        stream=sys.stderr,
    )

    try:
        neuron = CerebroNeuron()
        logging.info(neuron.invocation)

        if neuron.invocation.role == 'responder':
            # Responders run on entities (observables, alerts, cases) with optional context.
            obj_type = neuron.invocation.object_type
            obj_id = neuron.invocation.object_id
            observable_value = None

            if obj_type.startswith('observable:'):
                logging.info(
                    f'Responder run on observable id={obj_id!r} '
                    f'dataType={obj_type.removeprefix("observable:")!r}'
                )
                try:
                    obs_doc = neuron.thehive.get_observable(obj_id)
                except AttributeError:
                    logging.warning(
                        'Skipping TheHive fetch: client not initialized (set TH_URL)'
                    )
                except RequestException as exc:
                    logging.warning(f'TheHive get_observable failed: {exc}')
                else:
                    observable_value = obs_doc.get('data')
                    if observable_value is not None:
                        logging.info(f'Observable value from TheHive: {observable_value!r}')

            report = {
                'full': {
                    # in responder context the report needs to be short
                    'message': (
                        f'Execution went well! value={observable_value!r}'
                        if observable_value is not None
                        else 'Execution went well!'
                    ),
                },
                'operations': [
                    # operations require to identify with which entity
                    # we are working with
                ],
            }

        if neuron.invocation.role == 'analyzer':
            # Analyzers run on a single observable (type + value only).
            obs_type = neuron.invocation.object_type
            obs_value = neuron.invocation.object_value

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
                    # this needs to map an analyzer observable in TheHive schema
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
            logging.warning(f'Callback to Cerebro failed: {exc}')

    except Exception as e:
        logging.exception(f'Unhandled exception: {e}')
        raise SystemExit(1) from e
