# -*- coding: utf-8 -*-
"""TODO Docstring, used in the command line help text."""
import argparse
import logging

# from batch_calculator.read_rainfall_events import BuiReader
# from batch_calculator.StartSimulation import StartSimulation
# from batch_calculator.DownloadResults import DownloadResults
from batch_calculator.Batch import Batch
from threedi_api_client import ThreediApiClient

# from openapi_client import SimulationsApi

from openapi_client.api import ThreedimodelsApi

# from openapi_client.api import OrganisationsApi

logger = logging.getLogger(__name__)


def run_batch_calculator(**kwargs):

    if kwargs.get("verbose"):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    api_config = kwargs.get("api_config")

    client = ThreediApiClient(api_config)

    threedi_models = ThreedimodelsApi(client)
    # organisations = OrganisationsApi(client)

    # bui = BuiReader(kwargs["rain_files_dir"])

    model_id = threedi_models.threedimodels_read(12).id
    model_name = threedi_models.threedimodels_read(12).repository_slug
    org_id = kwargs["org_id"]

    # sim = StartSimulation(client, model_id, model_name, org_id, bui)

    # results = DownloadResults(
    #     client, sim.created_sim_id, sim.model_id, kwargs["results_dir"]
    # )

    Batch(  # TODO batch =
        kwargs.get("rain_files_dir"),
        client,
        model_id,
        model_name,
        org_id,
        kwargs.get("results_dir"),
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
    parser.add_argument("rain_files_dir")
    parser.add_argument("org_id")
    parser.add_argument("results_dir")
    return parser


def main():
    """Execute main program with multiprocessing."""
    try:
        return run_batch_calculator(**vars(get_parser().parse_args()))
    except SystemExit:
        raise


if __name__ == "__main__":
    main()
