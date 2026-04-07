import logging
import sys

from cerebro_neuron import CerebroNeuron

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        stream=sys.stderr,
    )
    try:
        neuron = CerebroNeuron()
        logging.info(neuron.args)

    except Exception as e:
        logging.exception(f'Unhandled exception: {e}')
        raise SystemExit()
