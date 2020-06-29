# -*- coding: utf-8 -*-
"""TODO Docstring, used in the command line help text."""
import argparse
import os
import logging
import numpy as np
import pandas

# from batch_calculator.read_rainfall_events import BuiReader
# from batch_calculator.StartSimulation import StartSimulation
# from batch_calculator.DownloadResults import DownloadResults
from batch_calculator.Batch import Batch
from batch_calculator.DownloadResults import DownloadResults
from threedi_api_client import ThreediApiClient

# from threedigrid.admin.gridadmin import GridH5Admin
from threedigrid.admin.gridresultadmin import GridH5AggregateResultAdmin

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

    model_name = threedi_models.threedimodels_read(kwargs["model_id"]).repository_slug

    batch = Batch(  # TODO batch =
        kwargs.get("rain_files_dir"),
        client,
        kwargs.get("model_id"),
        model_name,
        kwargs.get("org_id"),
        kwargs.get("ini_2d_water_level"),
        kwargs.get("results_dir"),
        kwargs.get("saved_state_url"),
    )

    nc_dir = batch.agg_dir
    gridadmin = batch.agg_dir + "/" + "gridadmin.h5"
    nr_years = int(kwargs["nr_years"])

    ## Read gridadmin file
    nc_files = [file for file in os.listdir(nc_dir) if file.endswith(".nc")]

    for i, aggregate_file in enumerate(nc_files):
        print(aggregate_file)
        ga = GridH5AggregateResultAdmin(gridadmin, os.path.join(nc_dir, aggregate_file))

        # Filter weir timeseries
        weir_data = (
            ga.lines.filter(content_type="v2_weir")
            .only("content_pk", "content_type", "q_cum")
            .timeseries(indexes=slice(None))
            .data
        )

        # Loop over weirs and add data to dataframe
        if i == 0:
            results = pandas.DataFrame(
                columns=["aggregate_netcdf", *weir_data["content_pk"]]
            )
        cumulative_discharge = [x for x in weir_data["q_cum"][-1]]
        results.loc[i] = [aggregate_file, *cumulative_discharge]

    # Find results for each weir
    stats = [1, 2, 5, 10]
    output = pandas.DataFrame(
        columns=[
            "weir_id",
            "overstortfrequentie",
            "gem_overstortvolume",
            "vuiluitworp",
            "t1",
            "t2",
            "t5",
            "t10",
        ]
    )
    for i, weir in enumerate(results.columns[1:]):
        weir_overstortfrequentie = int(sum(results[weir] > 0) / nr_years)
        weir_gem_overstortvolume = sum(results[weir]) / nr_years
        weir_vuiluitworp = weir_gem_overstortvolume * 0.25
        weir_tx_list = [
            np.percentile(results[weir], (1 - 1 / stat) * 100) for stat in stats
        ]
        output.loc[i] = [
            weir,
            weir_overstortfrequentie,
            weir_gem_overstortvolume,
            weir_vuiluitworp,
            *weir_tx_list,
        ]

    output.to_csv(
        os.path.join(kwargs["results_dir"], "vuilemissie_statistieken.csv"),
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
        "--api-config",
        default=os.path.abspath(".env"),
        help="Location of the .env file required for authentication",
    )
    parser.add_argument(
        "--org_id",
        default="61f5a464c35044c19bc7d4b42d7f58cb",
        help="UUID of the organisation used for the 3Di calculation",
    )
    parser.add_argument("model_id")
    parser.add_argument("rain_files_dir")
    parser.add_argument("ini_2d_water_level")
    parser.add_argument("results_dir")
    parser.add_argument("--saved_state_url")
    parser.add_argument(
        "nr_years",
        default="10",
        metavar="NR_YEARS",
        help="Amount of years the statistics are based on",
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
