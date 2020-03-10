# -*- coding: utf-8 -*-
"""TODO Docstring, used in the command line help text."""
import argparse
import logging

from batch_calculator.read_rainfall_events import BuiReader
from batch_calculator.StartSimulation import StartSimulation
from threedi_api_client import ThreediApiClient
from openapi_client import SimulationsApi

from openapi_client.api import ThreedimodelsApi
from openapi_client.api import OrganisationsApi

logger = logging.getLogger(__name__)


def run_batch_calculator(**kwargs):

    if kwargs.get("verbose"):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    api_config = kwargs.get("api_config")

    client = ThreediApiClient(api_config)
    sim = SimulationsApi(client)
    threedi_models = ThreedimodelsApi(client)
    organisations = OrganisationsApi(client)

    bui = BuiReader(kwargs["path"])

    model_id = threedi_models.threedimodels_read(12).id
    model_name = "v2_bergermeer"
    org_id = (
        organisations.organisations_list(name="Nelen & Schuurmans").results[0].unique_id
    )

    start_sim = StartSimulation(client, model_id, model_name, org_id, bui)


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
    parser.add_argument("org")
    return parser


def main():
    """Execute main program with multiprocessing."""
    try:
        return run_batch_calculator(**vars(get_parser().parse_args()))
    except SystemExit:
        raise


if __name__ == "__main__":
    main()
