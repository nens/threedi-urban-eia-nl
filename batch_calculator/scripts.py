# -*- coding: utf-8 -*-
"""TODO Docstring, used in the command line help text."""
import argparse
import logging

from batch_calculator.read_rainfall_events import BuiReader
from threedi_api_client import ThreediApiClient

logger = logging.getLogger(__name__)


def run_batch_calculator(**kwargs):

    if kwargs.get("verbose"):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    api_config = kwargs.get("api_config")

    client = ThreediApiClient(api_config)

    bui = BuiReader(kwargs["path"])
    # print(bui.duration,bui.file)

    # bui.parse_rain_timeseries()

# Start simulation function
def start_simulation(self, b):
    with output:
        my_sim = Simulation(
            name=self.sim_name.value,
            threedimodel=self._model_select.value,
            organisation=self._organisation_select.value,
            start_datetime=bui.start_datetime,
            duration=bui.duration
        )


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="verbose",
        default=False,
        help="Verbose output",
    )
    parser.add_argument("--api-config", default="")
    parser.add_argument("path")
    return parser


def main():
    """Execute main program with multiprocessing."""
    try:
        return run_batch_calculator(**vars(get_parser().parse_args()))
    except SystemExit:
        raise


if __name__ == "__main__":
    main()
