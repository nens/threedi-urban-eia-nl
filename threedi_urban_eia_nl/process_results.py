import json
import os
import shutil
import zipfile
from math import floor
from pathlib import Path
from typing import Dict, List
from urllib.request import urlretrieve

import click
import pandas as pd
from threedi_api_client import ThreediApi
from threedi_api_client.openapi.models import SimulationStatus
from threedi_api_client.versions import V3BetaApi
from threedigrid.admin.gridresultadmin import GridH5AggregateResultAdmin

from threedi_urban_eia_nl.rain_series_simulations import api_call, printProgressBar

def calculate_volume_error_events(netcdf_dir: Path, threshold: float | int):
    """
    Calculate volume error with respect to the volume of 0D outflow into 1D system
    Created on Mon May 18 14:09:04 2020

    @author:
    """
    print("Calculating volume error from rain events...")
    sim_results_dir = Path(netcdf_dir.absolute().parent, "simulations")
    sim_volume_error_dict = {}
    list_sim_ids_above_threshold = []
    
    # Loop over all simulation result folders (only folders! by f.is_dir())
    for i, sim_folder in enumerate([f for f in sim_results_dir.iterdir() if f.is_dir()]):
        sim_id = int(sim_folder.name.split("-")[0])
        flow_summary_file = sim_folder / "flow_summary.json"
        if not flow_summary_file.exists():
            print(f"WARNING: flow_summary.json not found for simulation {sim_id} in {flow_summary_file}. Skipping volume error calculation for this simulation, and moving it out of the simulations folder to avoid checking it again.")
            shutil.move(str(sim_folder), str(sim_folder.parent.parent / sim_folder.name))
            continue
        with flow_summary_file.open("r") as f:
            flow_summary = json.loads(f.read())
        zero_d_inflow = flow_summary["volume_balance"]["0D_inflow"]["value"]
        vol_error = flow_summary["volume_balance"]["maximum_volume_error"]["value"]
        vol_error_percentage = (
            vol_error / zero_d_inflow * 100 if zero_d_inflow != 0 else 0
        )
        
        sim_volume_error_dict[sim_id] = vol_error_percentage

        # Extract sim_ids with an volume error above threshold
        list_sim_ids_above_threshold.append(
            sim_id
        ) if vol_error_percentage > threshold else None

    return sim_volume_error_dict, list_sim_ids_above_threshold

def calculate_no_of_crashed_simulations(netcdf_dir: Path):
    """
    Calculate number of crashed simulations that are in folder 'crashed_simulations'
    Created on Mon May 18 14:09:04 2020

    @author:
    """
    print("Calculating number of crashed simulations...")
    crashed_sim_dir = Path(netcdf_dir.absolute().parent, "crashed_simulations")
    sim_ids_crashed = []
    
    # Loop over all crashed simulation result folders (only folders! by f.is_dir())
    for i, sim_folder in enumerate([f for f in crashed_sim_dir.iterdir() if f.is_dir()]):
        sim_id = sim_folder.name
        # add sim_id to list
        sim_ids_crashed.append(sim_id)

    return sim_ids_crashed

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

def dataframe_calculated_statistics(netcdf_dir: Path, results_cum: pd.DataFrame, results_cum_negative: pd.DataFrame, results_cum_positive: pd.DataFrame, nr_years: int, factor_successful_sims: float):
    """
    Compute weir statistics from netcdf files
    @author: Emile.deBadts
    """
    nan_results = {}
    # Find results for each weir
    output = pd.DataFrame(
        columns=[
            "weir_id",
            "frequency (active/year)",
            "average_volume (m3/year)",
            "negative_discharge_frequency (active/year)",
            "average_negative_discharge (m3/year)",
            "positive_discharge_frequency (active/year)",
            "average_positive_discharge (m3/year)",
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

        # correct cumulative volumes for amount of excluded events, if given
        # Assumptions: the excluded events are random and do not bias the results, so will not affect the T1, T2, T5, T10 calculations
        frequency = sum(results_cum[weir] > 0) * factor_successful_sims / nr_years
        average_volume = sum(results_cum[weir]) * factor_successful_sims / nr_years
        negative_discharge_freq = sum(results_cum_negative[weir] > 0) * factor_successful_sims / nr_years
        negative_discharge_vol = sum(results_cum_negative[weir]) * factor_successful_sims / nr_years
        positive_discharge_freq = sum(results_cum_positive[weir] > 0) * factor_successful_sims / nr_years
        positive_discharge_vol = sum(results_cum_positive[weir]) * factor_successful_sims / nr_years
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
            "WARNING: one or more weirs found which have NaN results in their "
            "cumulative discharge. Please check the nan_rows.json file for more "
            "information. This file contains weir id and netcdf file where the NaN "
            "values are found. "
        )
        results_file = netcdf_dir.parent / "nan_rows.json"
        with results_file.open("w") as f:
            json.dump(nan_results, f, indent=4, default=str)
    
    return output

def batch_calculation_statistics(netcdf_dir: Path, gridadmin: str, nr_years: int, extended_results: bool, threshold: float | int, correction_cum_vols: bool):
    """
    Compute weir statistics from netcdf files
    @author: Emile.deBadts
    """
    print("Processing statistics...")

    # Setup result pandas dataframe
    nc_files = [file for file in os.listdir(netcdf_dir) if file.endswith(".nc")]
    ga = GridH5AggregateResultAdmin(gridadmin, netcdf_dir / nc_files[0])
    weir_pks = ga.lines.weirs.content_pk
    results_cum = pd.DataFrame(columns=["aggregate_netcdf", *weir_pks])
    results_cum_negative = pd.DataFrame(columns=["aggregate_netcdf", *weir_pks])
    results_cum_positive = pd.DataFrame(columns=["aggregate_netcdf", *weir_pks])

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
    
    if extended_results == False:
        # Make output dataframe with calculated statistics
        output = dataframe_calculated_statistics(netcdf_dir, results_cum, results_cum_negative, results_cum_positive, nr_years, factor_successful_sims = 1)
    elif extended_results == True:
        # Make dataframe with calculated statistics, extended results include more details about volume errors
        # Rain events can be excluded based on the volume error with respect to the used rain volum
        sim_volume_error_dict, sim_ids_above_threshold = calculate_volume_error_events(netcdf_dir, threshold)
        sim_ids_crashed = calculate_no_of_crashed_simulations(netcdf_dir)

        # Convert 'aggregate_netcdf' column values to sim_id for all results DataFrames, to compare with df_vol_error
        for df_replace in [results_cum, results_cum_negative, results_cum_positive]:
            for i, row in df_replace.iterrows():
                # Extract sim_id from 'aggregate_netcdf' (e.g., 'aggregate_results_3di_sim_364648.nc' -> 364648)
                df_replace.loc[i, "aggregate_netcdf"] = int(str(row["aggregate_netcdf"]).split("_")[-1].split(".")[0])

        # Remove all rain events with volume error > threshold %
        dfs = [results_cum, results_cum_negative, results_cum_positive] # dfs to be cleaned
        dfs = [df[~df["aggregate_netcdf"].isin(sim_ids_above_threshold)] for df in dfs]
        results_cum, results_cum_negative, results_cum_positive = dfs

        if correction_cum_vols == True:
            # Calculate factors to scale results to account for excluded rain events (which will affect cumulative volumes and frequencies)
            total_successful_simulations = len(results_cum)
            total_simulations = total_successful_simulations+len(sim_ids_above_threshold)+len(sim_ids_crashed)
            factor_successful_sims = total_simulations / total_successful_simulations
            print(f"Number of simulations excluded of {total_simulations} total sims: based on volume error threshold: {len(sim_ids_above_threshold)}, based on crashes: {len(sim_ids_crashed)}.")
            print(f"Total excluded: {len(sim_ids_above_threshold)+len(sim_ids_crashed)}/{total_simulations}.")
        else:
            factor_successful_sims = 1
        
        # Make output dataframe with calculated statistics
        output = dataframe_calculated_statistics(netcdf_dir, results_cum, results_cum_negative, results_cum_positive, nr_years, factor_successful_sims)

        # Transpose results_cum, make each weir_id is a as a row, then merge with output on 'weir_id'
        weir_volumes_per_event = results_cum.set_index('aggregate_netcdf').T
        weir_volumes_per_event = weir_volumes_per_event.rename_axis('weir_id').reset_index()
        output = output.merge(weir_volumes_per_event, on='weir_id', how='left')

        # Add volume error information to output
        # Insert a new row as the first row in the output dataframe, then insert volume error values
        row_volume_error = pd.DataFrame([sim_volume_error_dict], columns=output.columns)
        output = pd.concat([row_volume_error, output], ignore_index=True)

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
            simulation_name: str = simulation[1]
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
                        sim_dir = simulations_dir / f"{simulation_id}-{simulation_name}"
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

    # Crashes feedback
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
@click.option(
    "-e",
    "--extended-results",
    type=bool,
    is_flag=True,
    default=False,
    help="Include extended results of all rain events in the statistics output csv [default: False]",
)
@click.option(
    "-t",
    "--threshold-vol-error",
    type=float|int,
    is_flag=True,
    default=1000000000,
    help="Volume error threshold above which simulations results are not included in statistics calculations [default: 1000000000, i.e., all]",
)
def process_results(
    created_simulations: Path,
    host: str,
    apikey: str,
    debug: bool,
    skip_download: bool,
    extended_results: bool, # TODO make it input argument! 
    threshold_vol_error: float | int, # TODO make it input argument!
    correction_cum_vols: bool, # TODO make it input argument!
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
            nr_years=10, #TODO: make dynamic
            extended_results=extended_results,
            threshold=threshold_vol_error,
            correction_cum_vols=correction_cum_vols,
        ).to_csv(
            str(Path(results_dir, "batch_calculator_statistics").with_suffix(".csv")),
            index=False,
        )


if __name__ == "__main__":
    process_results()
