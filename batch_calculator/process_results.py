import click
import json
import os
import shutil
import urllib

from batch_calculator.rain_series_simulations import printProgressBar
from batch_calculator.batch_calculation_statistics import batch_calculation_statistics
from pathlib import Path
from threedi_api_client import ThreediApi
from threedi_api_client.openapi.models import SimulationStatus
from threedi_api_client.versions import V3BetaApi
from time import sleep
from typing import (
    Dict,
    List,
)


def download_results(
    api: V3BetaApi,
    rain_event_simulations: List[Dict],
    results_dir: Path,
    threedimodel_id: int,
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

    remaining = [sim["id"] for sim in rain_event_simulations]
    crashes = []
    total = len(rain_event_simulations)
    while len(remaining) > 0:
        for simulation_id in remaining:
            printProgressBar(total - len(remaining), total, "Downloading result files")
            status: SimulationStatus = api.simulations_status_list(simulation_id)
            if status.name == "crashed":
                remaining.remove(simulation_id)
                crashes.append(simulation_id)
            elif status.name == "finished":
                # wait for files to be uploaded
                results = api.simulations_results_files_list(simulation_id).results
                if results == [] or (
                    results[0].file.state != "uploaded"
                    or results[1].file.state != "uploaded"
                    or results[2].file.state != "uploaded"
                ):
                    continue

                remaining.remove(simulation_id)
                simulation_dir = results_dir / Path(f"simulation-{simulation_id}")
                os.mkdir(simulation_dir)
                for result in results:
                    download = api.simulations_results_files_download(
                        result.id, simulation_id
                    )
                    if result.filename.startswith("agg"):
                        urllib.request.urlretrieve(
                            download.get_url,
                            Path(
                                aggregation_dir,
                                f"aggregate_results_3di_sim_{simulation_id}",
                            ).with_suffix(".nc"),
                        )
                    else:
                        urllib.request.urlretrieve(
                            download.get_url,
                            Path(simulation_dir, result.filename),
                        )
        sleep(0.1)

    # Download gridadmin
    download = api.threedimodels_gridadmin_download(threedimodel_id)
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
    "env_file",
    type=click.Path(exists=True, readable=True, path_type=Path),
)
def process_results(created_simulations: Path, env_file):
    """
    Download and process the results of the rain series simulations.
    Input is the created_simulations-{date}.json file from rain_series_simulations.py
    """
    with ThreediApi(env_file=env_file, version="v3-beta") as api:
        api: V3BetaApi

        results_dir = created_simulations.absolute().parent
        with Path(results_dir, "created_simulations.json").open("r") as f:
            created_simulations = json.loads(f.read())

        download_results(
            api,
            created_simulations["rain_event_simulations"],
            results_dir,
            created_simulations["threedimodel_id"],
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
