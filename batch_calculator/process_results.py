import click
import json
import os
import pandas
import shutil
import urllib
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
from time import sleep
from typing import (
    Dict,
    List,
)
from threedigrid.admin.gridresultadmin import GridH5AggregateResultAdmin


def repetition_time_volumes(weir_results, n, stats=[1, 2, 5, 10]):
    """
    Created on Mon May 18 14:09:04 2020

    @author: Emile.deBadts
    """
    sorted_weir_results = sorted(list(weir_results), reverse=True)
    print(sorted_weir_results)
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


def batch_calculation_statistics(netcdf_dir, gridadmin, nr_years):
    """
    Created on Mon May 18 14:09:04 2020

    @author: Emile.deBadts
    """

    nc_files = [file for file in os.listdir(netcdf_dir) if file.endswith(".nc")]
    ga = GridH5AggregateResultAdmin(gridadmin, os.path.join(netcdf_dir, nc_files[0]))
    weir_pks = ga.lines.weirs.content_pk
    results = pandas.DataFrame(columns=["aggregate_netcdf", *weir_pks])

    for i, aggregate_file in enumerate(nc_files):
        ga = GridH5AggregateResultAdmin(
            gridadmin, os.path.join(netcdf_dir, aggregate_file)
        )
        weir_data = ga.lines.filter(content_type="v2_weir").only(
            "content_pk", "content_type", "q_cum"
        )
        cumulative_discharge = [abs(x) for x in (weir_data.q_cum)[-1]]
        results.loc[i] = [aggregate_file, *cumulative_discharge]

    # Find results for each weir
    output = pandas.DataFrame(
        columns=["weir_id", "frequency", "average_volume", "t1", "t2", "t5", "t10"]
    )

    for i, weir in enumerate(results.columns[1:]):
        frequency = float(sum(results[weir] > 0) / nr_years)
        average_volume = sum(results[weir]) / nr_years
        weir_tx_list = [
            *repetition_time_volumes(weir_results=results[weir], n=nr_years)
        ]

        output.loc[i] = [
            weir,
            frequency,
            average_volume,
            *weir_tx_list,
        ]

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

    aggregation_dir = results_dir / Path("aggregation_netcdfs")
    os.mkdir(aggregation_dir)

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
                remaining.remove(simulation_id)
                crashes.append(simulation_id)
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
                        urllib.request.urlretrieve(
                            download.get_url,
                            Path(
                                aggregation_dir,
                                f"aggregate_results_3di_sim_{simulation_id}",
                            ).with_suffix(".nc"),
                        )

                    if debug and result.filename.startswith("log"):
                        "Download log files and unzip"
                        simulation_dir = results_dir / Path(
                            f"simulation-{simulation_id}-isahw{isahw}"
                        )
                        os.mkdir(simulation_dir)
                        download = api_call(
                            api.simulations_results_files_download,
                            *(
                                result.id,
                                simulation_id,
                            ),
                        )
                        urllib.request.urlretrieve(
                            download.get_url,
                            Path(simulation_dir, result.filename),
                        )
                        with zipfile.ZipFile(
                            simulation_dir / f"log_files_sim_{simulation_id}.zip", "r"
                        ) as zip:
                            zip.extractall(simulation_dir)

            sleep(1)

    # Download gridadmin
    download = api_call(api.threedimodels_gridadmin_download, threedimodel_id)
    urllib.request.urlretrieve(
        download.get_url,
        Path(results_dir, "gridadmin").with_suffix(".h5"),
    )

    printProgressBar(total, total, "Downloading result files")
    for crash in crashes:
        print(f"Warning: simulation {crash} crashed")


@click.command()
@click.argument(
    "created_simulations",
    type=click.Path(exists=True, readable=True, path_type=Path),
)
@click.argument(
    "user",
    type=str,
)
@click.option(
    "-h",
    "--host",
    type=str,
    default="https://api.3di.live",
)
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
)
@click.option(
    "--debug",
    type=bool,
    default=False,
)
def process_results(
    created_simulations: Path, user: str, host: str, password: str, debug: bool
):
    """
    Download and process the results of the rain series simulations.
    Input is the created_simulations-{date}.json file from rain_series_simulations.py

    debug option downloads log files per simulation.
    """
    config = {
        "THREEDI_API_HOST": host,
        "THREEDI_API_USERNAME": user,
        "THREEDI_API_PASSWORD": password,
    }
    with ThreediApi(config=config, version="v3-beta") as api:
        api: V3BetaApi

        results_dir = created_simulations.absolute().parent
        with Path(created_simulations).open("r") as f:
            created_simulations = json.loads(f.read())

        download_results(
            api,
            created_simulations["rain_event_simulations"],
            results_dir,
            created_simulations["threedimodel_id"],
            debug,
        )

        # Calculate statistics
        batch_calculation_statistics(
            netcdf_dir=str(Path(results_dir, "aggregation_netcdfs")),
            gridadmin=str(Path(results_dir, "gridadmin").with_suffix(".h5")),
            nr_years=10,
        ).to_csv(
            str(Path(results_dir, "batch_calculator_statistics").with_suffix(".csv")),
            index=False,
        )


if __name__ == "__main__":
    process_results()
