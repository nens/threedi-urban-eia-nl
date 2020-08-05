# -*- coding: utf-8 -*-
"""TODO Docstring, used in the command line help text."""
import argparse
import os
import logging
import numpy as np


from batch_calculator.Batch import Batch
from batch_calculator.DownloadResults import DownloadResults
from batch_calculator.batch_calculation_statistics import (
    batch_calculation_statistics,
    repetition_time_volumes,
)
from threedi_api_client import ThreediApiClient
from openapi_client.api import ThreedimodelsApi
from getpass import getpass, getuser


logger = logging.getLogger(__name__)


def run_batch_calculator(**kwargs):

    if kwargs.get("verbose"):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    # Authentication
    API_HOST = "https://api.3di.live/v3.0"
    USERNAME = getuser()
    PASSWORD = getpass("Password: ")
    config = {"API_HOST": API_HOST, "API_USERNAME": USERNAME, "API_PASSWORD": PASSWORD}
    client = ThreediApiClient(config=config)

    # Models
    threedi_models = ThreedimodelsApi(client)
    model_name = threedi_models.threedimodels_read(kwargs["model_id"]).repository_slug

    batch = Batch(
        rain_files_dir = kwargs.get("rain_files_dir"),
        client = client,
        model_id = kwargs.get("model_id"),
        model_name = model_name,
        org_id = kwargs.get("org_id"),
        results_dir = kwargs.get("results_dir"),
        ini_2d_water_level_constant = kwargs.get("ini_2d_water_level_constant"),
        saved_state_url = kwargs.get("saved_state_url"),
    )

    # Script Emile
    nc_dir = batch.agg_dir
    gridadmin = os.path.join(nc_dir, "gridadmin.h5")
    nr_years = int(kwargs["nr_years"])

    batch_calculation_stats_table = batch_calculation_statistics(
        netcdf_dir=nc_dir, gridadmin=gridadmin, nr_years=nr_years
    )

    batch_calculation_stats_table.to_csv(
        os.path.join(kwargs["results_dir"], "batch_calculator_statistics.csv"),
        index=False,
    )


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="verbose",
        default=False,
        help="Verbose output",
    )
    parser.add_argument(
        "--org_id",
        default="61f5a464c35044c19bc7d4b42d7f58cb",
        help="UUID of the organisation used for the 3Di calculation",
    )
    parser.add_argument(
        "model_id",
        metavar="MODEL_ID",
        help="id number of the model as listed on: https://api.3di.live/v3.0/threedimodels/",
    )
    parser.add_argument(
        "rain_files_dir",
        metavar="RAIN_FILES_DIR",
        help="The directory in which all the rain files are located",
    )
    parser.add_argument(
        "results_dir",
        metavar="RESULTS_DIR",
        help="The directory in which all downloaded results will be stored",
    )
    parser.add_argument(
        "--ini_2d_water_level_constant",
        metavar="INI_2D_WATER_LEVEL",
        help="The initial 2D water level constant in mNAP",
    )
    parser.add_argument(
        "--saved_state_url",
        metavar="SAVED_STATE_URL",
        help="The url of the saved state that will be used at the start of the simulation. Saved states can be found here: https://api.3di.live/v3.0/files/",
    )
    parser.add_argument(
        "--nr_years",
        default="10",
        metavar="NR_YEARS",
        choices=["10", "25"],
        help="Batch calculation length (10 or 25 years)",
    )
    return parser


def main():
    """Execute main program with multiprocessing."""
    try:
        return run_batch_calculator(**vars(get_parser().parse_args()))
    except SystemExit:
        raise


if __name__ == "__main__":
    main()
