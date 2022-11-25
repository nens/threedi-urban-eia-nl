import click
import json
import numpy as np
import os
import pandas
import shutil
import zipfile

from batch_calculator.rain_series_simulations import (
    printProgressBar,
    api_call,
)
from math import floor
from pathlib import Path
from threedi_api_client import ThreediApi
from threedi_api_client.openapi.models import SimulationStatus
from threedi_api_client.versions import V3BetaApi
from typing import (
    Dict,
    List,
)
from threedigrid.admin.gridresultadmin import GridH5AggregateResultAdmin
from urllib.request import urlretrieve


def repetition_time_volumes(weir_results, n, stats=[1, 2, 5, 10]):
    """
    Created on Mon May 18 14:09:04 2020

    @author: Emile.deBadts
    """
    sorted_weir_results = sorted(list(weir_results), reverse=True)
    if n == 10:
        T_volume_list = []
        for T in stats:
            if T == 5:
                volume = sorted_weir_results[1] - 0.48 * (
                    sorted_weir_results[1] - sorted_weir_results[2]
                )
                T_volume_list += [volume]
            elif T == 10:
                volume = sorted_weir_results[0] - 0.46 * (
                    sorted_weir_results[0] - sorted_weir_results[1]
                )
                T_volume_list += [volume]
            else:
                T_volume_list += [sorted_weir_results[int(n / T) - 1]]

    if n == 25:
        T_volume_list = []
        for T in stats:
            if (n / T).is_integer():
                T_volume_list += [sorted_weir_results[int(n / T) - 1]]
            else:
                volume = sorted_weir_results[floor(n / T) - 1] - 0.5 * (
                    sorted_weir_results[floor(n / T) - 1]
                    - sorted_weir_results[floor(n / T)]
                )
                T_volume_list += [volume]

    return T_volume_list


def batch_calculation_statistics(netcdf_dir: Path, gridadmin: str, nr_years: int):
    """
    Compute weir statistics from netcdf files
    @author: Emile.deBadts
    """
    print("Processing statistics...")

    # Setup result pandas dataframe
    nc_files = [file for file in os.listdir(netcdf_dir) if file.endswith(".nc")]
    ga = GridH5AggregateResultAdmin(gridadmin, netcdf_dir / nc_files[0])
    weir_pks = ga.lines.weirs.content_pk
    results_cum = pandas.DataFrame(columns=["aggregate_netcdf", *weir_pks])
    results_cum_negative = pandas.DataFrame(columns=["aggregate_netcdf", *weir_pks])
    results_cum_positive = pandas.DataFrame(columns=["aggregate_netcdf", *weir_pks])
    nan_results = {}

    # Get cumulative discharge for all weirs
    for i, aggregate_file in enumerate(nc_files):
        ga = GridH5AggregateResultAdmin(gridadmin, netcdf_dir / aggregate_file)
        weir_data = ga.lines.filter(content_type="v2_weir").only(
            "content_pk",
            "content_type",
            "q_cum",
            "q_cum_negative",
            "q_cum_positive",
        )
        cumulative_discharge = [abs(x) for x in (weir_data.q_cum)[-1]]
        negative_discharge = [abs(x) for x in (weir_data.q_cum_negative)[-1]]
        positive_discharge = [abs(x) for x in (weir_data.q_cum_positive)[-1]]
        results_cum.loc[i] = [aggregate_file, *cumulative_discharge]
        results_cum_negative.loc[i] = [aggregate_file, *negative_discharge]
        results_cum_positive.loc[i] = [aggregate_file, *positive_discharge]

    # Find results for each weir
    output = pandas.DataFrame(
        columns=[
            "weir_id",
            "frequency (active/year)",
            "average_volume (m3/year)",
            "negative_discharge_frequency (active/year)",
            "average_negative_discharge (m3/year)",
            "positive_discharge_frequency (active/year)",
            "average_positive discharge (m3/year)",
            "t1 (m3)",
            "t2 (m3)",
            "t5 (m3)",
            "t10 (m3)",
        ]
    )

    for i, weir in enumerate(results_cum.columns[1:]):
        nan_rows = results_cum[results_cum[weir].isnull()]
        if len(nan_rows) > 0:
            nan_results[int(weir)] = nan_rows["aggregate_netcdf"].values

        frequency = sum(results_cum[weir] > 0) / nr_years
        average_volume = sum(results_cum[weir]) / nr_years
        negative_discharge_freq = sum(results_cum_negative[weir] > 0) / nr_years
        negative_discharge_vol = sum(results_cum_negative[weir]) / nr_years
        positive_discharge_freq = sum(results_cum_positive[weir] > 0) / nr_years
        positive_discharge_vol = sum(results_cum_positive[weir]) / nr_years
        weir_tx_list = [
            *repetition_time_volumes(weir_results=results_cum[weir], n=nr_years)
        ]

        output.loc[i] = [
            weir,
            frequency,
            average_volume,
            negative_discharge_freq,
            negative_discharge_vol,
            positive_discharge_freq,
            positive_discharge_vol,
            *weir_tx_list,
        ]

    if len(nan_results) > 0:
        print(
            "WARNING: one or more weirs found which have NaN results in their cumulative "
            "discharge. Please check the nan_rows.json file for more information. "
            "This file contains weir id and netcdf file where the NaN values are found. "
        )
        results_file = netcdf_dir.parent / "nan_rows.json"
        with results_file.open("w") as f:
            json.dump(nan_results, f, indent=4, default=str)

    return output


def download_results(
    api: V3BetaApi,
    rain_event_simulations: List[Dict],
    results_dir: Path,
    threedimodel_id: int,
    debug: bool,
) -> None:
    """
    Download results by checking remaining simulations for uploaded files.
    Place aggregation netcdfs in /aggregation_netcdf folder.
    Place other result files in simulation-{id} folder.
    """

    # First clean results dir
    for file in results_dir.iterdir():
        if file.is_dir():
            shutil.rmtree(Path(results_dir, file))

    aggregation_dir = results_dir / "aggregation_netcdfs"
    aggregation_dir.mkdir()

    simulations_dir = results_dir / "simulations"
    remaining = [(sim["id"], sim["name"]) for sim in rain_event_simulations]
    crashes = []
    total = len(rain_event_simulations)
    while len(remaining) > 0:
        for simulation in remaining:
            simulation_id: int = simulation[0]
            isahw: str = simulation[1].split("isahw")[1]
            printProgressBar(total - len(remaining), total, "Downloading result files")
            status: SimulationStatus = api_call(
                api.simulations_status_list, simulation_id
            )
            if status.name == "crashed":
                remaining.remove(simulation)
                crashes.append(simulation)
            elif status.name == "finished":
                # wait for files to be uploaded
                results = api_call(
                    api.simulations_results_files_list, simulation_id
                ).results
                if results == [] or (
                    results[0].file.state != "uploaded"
                    or results[1].file.state != "uploaded"
                    or results[2].file.state != "uploaded"
                ):
                    continue

                remaining.remove(simulation)
                for result in results:
                    if result.filename.startswith("agg"):
                        download = api_call(
                            api.simulations_results_files_download,
                            *(
                                result.id,
                                simulation_id,
                            ),
                        )
                        urlretrieve(
                            download.get_url,
                            Path(
                                aggregation_dir,
                                f"aggregate_results_3di_sim_{simulation_id}",
                            ).with_suffix(".nc"),
                        )

                    if debug and result.filename.startswith("log"):
                        "Download log files and unzip"
                        sim_dir = simulations_dir / f"{simulation_id}-isahw{isahw}"
                        sim_dir.mkdir(parents=True)
                        download = api_call(
                            api.simulations_results_files_download,
                            *(
                                result.id,
                                simulation_id,
                            ),
                        )
                        urlretrieve(
                            download.get_url,
                            Path(sim_dir, result.filename),
                        )
                        with zipfile.ZipFile(
                            sim_dir / f"log_files_sim_{simulation_id}.zip", "r"
                        ) as zip:
                            zip.extractall(sim_dir)

    printProgressBar(total, total, "Downloading result files")

    # Download gridadmin
    download = api_call(api.threedimodels_gridadmin_download, threedimodel_id)
    urlretrieve(
        download.get_url,
        Path(results_dir, "gridadmin").with_suffix(".h5"),
    )

    # Carshes feedback
    if len(crashes) > 0:
        print(
            f"WARNING: {len(crashes)} simulations crashed, see crashed_simulations.json"
        )
        results_file = results_dir / "crashed_simulations.json"
        with results_file.open("w") as f:
            json.dump(crashes, f, indent=4, default=str)


@click.command()
@click.argument(
    "created_simulations",
    type=click.Path(exists=True, readable=True, path_type=Path),
)
@click.option(
    "-h",
    "--host",
    type=str,
    default="https://api.3di.live",
    help="Host to run batch calculation on",
)
@click.option(
    "--apikey",
    prompt=True,
    hide_input=True,
)
@click.option(
    "-d",
    "--debug",
    type=bool,
    is_flag=True,
    default=False,
    help="Download simulation logs to debug potential issues [default: False]",
)
@click.option(
    "-s",
    "--skip-download",
    type=bool,
    is_flag=True,
    default=False,
    help="Skip downloading (aggregation) result files [default: False]",
)
def process_results(
    created_simulations: Path,
    host: str,
    apikey: str,
    debug: bool,
    skip_download: bool,
):
    """
    Download and process the results of the rain series simulations.
    Input is the created_simulations-{date}.json file from rain_series_simulations.py

    debug option downloads log files per simulation.
    """
    config = {
        "THREEDI_API_HOST": host,
        "THREEDI_API_PERSONAL_API_TOKEN": apikey,
    }
    with ThreediApi(config=config, version="v3-beta") as api:
        api: V3BetaApi

        results_dir = created_simulations.absolute().parent
        with Path(created_simulations).open("r") as f:
            created_simulations = json.loads(f.read())

        if not skip_download:
            download_results(
                api,
                created_simulations["rain_event_simulations"],
                results_dir,
                created_simulations["threedimodel_id"],
                debug,
            )

        # Calculate statistics
        batch_calculation_statistics(
            netcdf_dir=Path(results_dir, "aggregation_netcdfs"),
            gridadmin=str(Path(results_dir, "gridadmin").with_suffix(".h5")),
            nr_years=10,
        ).to_csv(
            str(Path(results_dir, "batch_calculator_statistics").with_suffix(".csv")),
            index=False,
        )


if __name__ == "__main__":
    process_results()
