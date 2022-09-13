from urllib.request import urlretrieve
from venv import create
import click
import numpy as np
import json
import os
import shutil
import pytz
import netCDF4 as nc4
import zipfile


from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from threedi_api_client import ThreediApi
from threedi_api_client.files import upload_file
from threedi_api_client.openapi.exceptions import ApiException
from threedi_api_client.openapi.models import (
    Action,
    FromTemplate,
    Progress,
    Revision,
    SavedStateOverview,
    Simulation,
    SimulationStatus,
    Template,
    ThreediModel,
    UploadEventFile,
)
from threedi_api_client.versions import V3BetaApi
from time import sleep
from typing import (
    Dict,
    List,
)

RAIN_EVENTS_START_DATE = datetime(1955, 1, 1)
REQUIRED_AGGREGATION_METHODS = {"cum", "cum_negative", "cum_positive"}
API_429_TIMEOUT = 60
TIMEOUT = 5


def api_call(call, *args, **kwargs):
    try:
        result = call(*args, **kwargs)
    except ApiException as e:
        if e.status == 429:
            sleep(API_429_TIMEOUT)
            return api_call(call, *args, **kwargs)
        else:
            raise e

    return result


def printProgressBar(iteration, total, text, length=100):
    percent = int(100 * (iteration / total))
    bar = "#" * percent + "-" * (length - percent)
    print(f"\r{text} |{bar}| {percent}% Completed", end="\r")
    if iteration == total:
        print()


def download_sqlite(api: V3BetaApi, threedimodel_id: int, results_dir: Path) -> Path:
    print("Downloading and validating sqlite...")
    threedimodel: ThreediModel = api.threedimodels_read(threedimodel_id)
    revision: Revision = api.schematisations_revisions_read(
        threedimodel.revision_id,
        schematisation_pk=threedimodel.schematisation_id,
    )
    if revision.sqlite is None or revision.sqlite.file.state != "uploaded":
        raise ValueError("The revision has no SQLite.")

    download = api.schematisations_revisions_sqlite_download(
        threedimodel.revision_id,
        schematisation_pk=threedimodel.schematisation_id,
    )
    path = results_dir / revision.sqlite.file.filename
    urlretrieve(download.get_url, path)

    if path.suffix.lower() == ".zip":
        # Extract sqlite from zip
        with path.open("rb") as f:
            zf = zipfile.ZipFile(f)
            for fn in zf.namelist():
                if fn.lower().endswith(".sqlite"):
                    zf.extract(fn, path=path.parent)
                    return path.parent / fn
            else:
                raise FileNotFoundError(
                    f"Could not find an .sqlite in zipfile {path}"
                )
            
    return path


def validate_sqlite(sqlite_path: Path):
    engine = create_engine(f"sqlite:///{sqlite_path}")
    session = Session(engine)

    query = "SELECT timestep, aggregation_method FROM v2_aggregation_settings WHERE flow_variable='discharge'"
    rows = [row for row in session.execute(query)]
    timesteps = np.array([row[0] for row in rows])
    aggregation_methods = set([row[1] for row in rows])

    if not np.all(timesteps == 3600):
        raise ValueError(
            "All timestep fields for discharge in aggregation settings should be 3600."
        )

    if aggregation_methods != REQUIRED_AGGREGATION_METHODS:
        raise ValueError(
            "SQLite does not contain correct aggregation settings for discharge. "
            f"Required aggregation settings are: {REQUIRED_AGGREGATION_METHODS}. "
            f"Current aggregation settings: {aggregation_methods}"
        )


def create_simulation(
    api: V3BetaApi,
    threedimodel_id: int,
    organisation: str,
    duration: int,
    start_datetime: str,
    simulation_name="rain series calculation",
) -> Simulation:
    """Create simulation from threedimodel simulation template."""
    result = api_call(
        api.simulation_templates_list,
        **{"simulation__threedimodel__id": threedimodel_id},
    )
    if len(result.results) == 0:
        raise ValueError("No simulation template for ThreediModel")

    template: Template = result.results[0]
    from_template = FromTemplate(
        template=template.id,
        name=simulation_name,
        organisation=organisation,
        duration=duration,
        start_datetime=start_datetime,
    )

    simulation = api_call(
        api.simulations_from_template,
        from_template,
    )
    return simulation


def await_simulation_completion(api: V3BetaApi, simulation: Simulation) -> None:
    while True:
        status: SimulationStatus = api_call(api.simulations_status_list, simulation.id)
        if status.name == "crashed":
            raise ValueError("DWF initialization simulation crashed")
        elif status.name != "finished":
            try:
                progress: Progress = api_call(
                    api.simulations_progress_list, simulation.id
                )
                printProgressBar(
                    progress.percentage, 100, f"Simulation {simulation.id}"
                )
            except ApiException as e:  # no progress while initializing
                if "No progress" not in e.body:
                    raise e
            finally:
                sleep(TIMEOUT)
        else:
            return


def create_saved_states(
    api: V3BetaApi, simulation: Simulation
) -> List[SavedStateOverview]:
    """Create saved states from simulation."""
    TWO_DAYS = 60 * 60 * 24 * 2
    saved_states = [
        api_call(
            api.simulations_create_saved_states_timed_create,
            simulation.id,
            **{"data": {"time": i * 60 * 60 + TWO_DAYS, "name": f"DWF hour {i}"}},
        )
        for i in range(24)
    ]

    return saved_states


def get_saved_states(
    api: V3BetaApi, simulation: Simulation
) -> List[SavedStateOverview]:
    results = []
    states = api_call(
        api.simulations_create_saved_states_timed_list, simulation.id, **{"limit": 100}
    )
    for i in range(24):
        for state in states.results:
            if state.name == f"DWF hour {i}":
                results.append(state)
                break

    return results


def convert_to_netcdf(rain_files_dir: Path) -> List[Dict]:
    """Read timeseries data, convert to m/s, and write to netcdf file."""

    # Make sure netcdf results folder exists and is empty
    try:
        os.mkdir("netcdf_rain_files")
    except FileExistsError:
        shutil.rmtree("netcdf_rain_files")
        os.mkdir("netcdf_rain_files")

    result = []
    filenames = [f for f in rain_files_dir.iterdir() if f.is_file()]
    for filename in filenames:
        # retrievie rain timeseries data
        with open(filename, "r") as f:
            timeseries = np.array(
                [
                    [int(row.split(",")[0]), float(row.split(",")[1])]
                    for row in f.read().split("\n")
                    if row
                ]
            )

        if timeseries[0, 0] != 0:
            raise ValueError(f"{filename}: first timestamp should be 0")
        if timeseries[-1, 1] != 0:
            print(f"Warning: {filename.name} last rain intensity value is not 0")

        # parse datetime from filename (NL datetime to UTC to timezone unaware)
        filename_date = (
            datetime.strptime(filename.name.split()[-1], "%Y%m%d%H%M%S")
            .astimezone(tz=pytz.timezone("Europe/Amsterdam"))
            .astimezone(tz=pytz.UTC)
            .replace(tzinfo=None)
        )

        rain_event_start_date = RAIN_EVENTS_START_DATE + (
            filename_date - RAIN_EVENTS_START_DATE
        )
        rain_event_start_seconds = (
            rain_event_start_date - RAIN_EVENTS_START_DATE
        ).total_seconds()

        # Convert from [mm/timestep in minutes] to [mm/h]
        timesteps = np.diff(timeseries[:, 0])
        values_converted = timeseries[:-1, 1] / (timesteps / 60)
        values_converted = np.append(
            values_converted, timeseries[-1, 1] / (timesteps[-1] / 60)
        )
        time = timeseries[:, 0] * 60 + rain_event_start_seconds

        path = Path("netcdf_rain_files") / (filename.name + ".nc")
        result.append(
            {
                "file": path,
                "duration": timeseries[-1, 0] * 60,
                "start_date": rain_event_start_date,
            }
        )

        # # Create netcdf
        # netcdf = h5py.File(
        #     path,
        #     mode="w",
        # )

        # # Global attributes
        # netcdf.attrs["title"] = bytes(filename.name, encoding="utf-8")
        # netcdf.attrs["institution"] = b"Nelen & Schuurmans"
        # netcdf.attrs["SIMULATION_OFFSET"] = 0
        # netcdf.attrs["SIMULATION_START_TIMESTEP"] = 0

        # # Datasets

        # netcdf.create_dataset(
        #     "SIMULATION_START_TIMESTEP",
        #     data=np.array([0]),
        #     dtype=np.int32,
        # )
        # # one = netcdf.create_dataset("one", np.array([0.0], dtype=np.float64), dtype=np.float64)
        # time = netcdf.create_dataset("time", data=time, dtype=np.float64)
        # values = netcdf.create_dataset(
        #     "values", data=values_converted, dtype=np.float64
        # )

        # # Dataset attributes
        # # one.attrs["_Netcdf4Dimid"] = 1
        # time.attrs["_Netcdf4Dimid"] = 0
        # time.attrs["axis"] = b"T"
        # time.attrs["calendar"] = b"standard"
        # time.attrs["long_name"] = b"Time"
        # time.attrs["standard_name"] = b"time"
        # time.attrs["units"] = b"seconds since 1955-01-01 00:00:00.0 +0000'"
        # values.attrs["_FillValue"] = np.array([-9999], dtype=np.int32)
        # values.attrs["units"] = b"mm/h"

        # # Set time as coordinate for values
        # # one.make_scale("one")
        # time.make_scale("time")
        # values.dims[0].attach_scale(time)
        # # values.dims[0].attach_scale(one)
        # netcdf.close()

        f = nc4.Dataset(path, "w")
        f.CDI = "Climate Data Interface version ?? (httpf.//mpimet.mpg.de/cdi)"
        f.Conventions = "CF-1.5"
        f.GDAL_AREA_OR_POINT = "Area"
        f.GDAL = "GDAL 2.2.3, released 2017/11/20"
        f.NCO = "4.7.2"
        f.CDO = "Climate Data Operators version 1.9.3 (http://mpimet.mpg.de/cdo)"
        # f.OFFSET = 0
        # f.SIMULATION_OFFSET = 0
        # f.SIMULATION_START_TIMESTEP = 0

        f.createDimension("time", None)  # infinite size
        f.createDimension("one", 1)

        time_var = f.createVariable("time", np.float64, ("time",))
        time_var.standard_name = "time"
        time_var.long_name = "Time"
        time_var.units = "seconds since 1955-01-01 00:00:00.0 +0000"
        time_var.calendar = "standard"
        time_var.axis = "T"

        sim_start_var = f.createVariable("SIMULATION_START_TIMESTEP", np.int64, ())

        values_var = f.createVariable(
            "values", np.float64, ("time", "one"), fill_value=-9999
        )
        values_var.units = "mm/h"

        time_var[:] = time
        values_var[:] = values_converted * 10e3
        sim_start_var[:] = np.array([0])

        f.close()

    return result


def create_simulations_from_netcdf_rain_events(
    api: V3BetaApi,
    saved_states: List,
    netcdfs: List[Dict],
    threedimodel_id: int,
    organisation_id: str,
) -> List[Simulation]:
    """
    Read start time from netcf filename and create simulations with the corresponding
    initial state from the DWF runs. Create file timeseries rain from netcdf data.
    Save created simulations to JSON as fallback.
    """
    rain_event_simulations = []
    for i, netcdf in enumerate(netcdfs):
        printProgressBar(i + 1, len(netcdfs), "Creating rain event simulations")
        filepath = netcdf["file"]
        start_date = netcdf["start_date"]

        # create simulation and set initial state
        simulation = create_simulation(
            api,
            threedimodel_id,
            organisation_id,
            netcdf["duration"],
            start_date,
            f"rain series calculation {filepath.name.split('.')[0]}",
        )
        api_call(
            api.simulations_initial_saved_state_create,
            simulation.id,
            **{"data": {"saved_state": saved_states[start_date.hour].id}},
        )

        upload: UploadEventFile = api_call(
            api.simulations_events_rain_timeseries_netcdf_create,
            simulation.id,
            **{"data": {"filename": filepath.name}},
        )
        upload_file(upload.put_url, filepath)

        rain_event_simulations.append(simulation)

    # Start simulation if netcdf is processed
    print("Starting rain event simulations...")
    started_simulations = []
    while len(rain_event_simulations) > 0:
        for simulation in rain_event_simulations:
            netcdf = api_call(
                api.simulations_events_rain_timeseries_netcdf_list, simulation.id
            ).results[0]
            if netcdf.file.state == "processed":
                started_simulations.append(simulation)
                rain_event_simulations.remove(simulation)
                api_call(
                    api.simulations_actions_create,
                    *(
                        simulation.id,
                        Action(name="queue"),
                    ),
                )
            elif netcdf.file.state == "error":
                print(
                    f"Warning: error processing netcdf for simulation {simulation.id}.",
                    netcdf.file.state_description,
                )
            sleep(TIMEOUT)

    return started_simulations


def create_simulations_from_rain_events(
    api: V3BetaApi,
    saved_states: List,
    threedimodel_id: int,
    organisation_id: str,
    rain_files_dir: Path,
) -> List[Simulation]:
    """
    Read start time from rain files filename and create simulations with the corresponding
    initial state from the DWF runs. Create timeseries rain event from file data.
    Save created simulations to JSON as fallback.
    """
    rain_event_simulations = []
    warnings = []
    files = [f for f in rain_files_dir.iterdir() if f.is_file()]
    for i, file in enumerate(files):
        printProgressBar(i + 1, len(files), "Creating rain event simulations")
        # retrievie rain timeseries data
        with open(file, "r") as f:
            timeseries = np.array(
                [
                    [int(row.split(",")[0]), float(row.split(",")[1])]
                    for row in f.read().split("\n")
                    if row
                ]
            )

        if timeseries[0, 0] != 0:
            raise ValueError(f"{file.name}: first timestamp should be 0")
        if timeseries[-1, 1] != 0:
            warnings.append(f"Warning: {file.name} last rain intensity value is not 0")

        # parse datetime from filename (NL datetime to UTC to timezone unaware)
        filename_date = (
            datetime.strptime(file.name.split()[-1], "%Y%m%d%H%M%S")
            .astimezone(tz=pytz.timezone("Europe/Amsterdam"))
            .astimezone(tz=pytz.UTC)
            .replace(tzinfo=None)
        )

        # Convert from [mm/timestep in minutes] to [m/s]
        timesteps = np.diff(timeseries[:, 0])
        values_converted = timeseries[:-1, 1] / (timesteps * 1000) / 60
        values_converted = np.append(
            values_converted, timeseries[-1, 1] / (timesteps[-1] * 1000) / 60
        )
        time = timeseries[:, 0] * 60

        # create simulation and set initial state
        simulation = create_simulation(
            api,
            threedimodel_id,
            organisation_id,
            time[-1] + 30 * 60,  # extend the simulation 30 minutes to be safe
            filename_date,
            f"rain series calculation {file.name.split('.')[0]}",
        )
        api_call(
            api.simulations_initial_saved_state_create,
            simulation.id,
            **{"data": {"saved_state": saved_states[filename_date.hour].id}},
        )

        for i in range((len(time) // 300) + 1):
            time_slice = time[i * 300 : (i + 1) * 300]
            time_slice_offset = time_slice - time_slice[0]
            values_slice = values_converted[i * 300 : (i + 1) * 300]
            values = [
                [x[0], x[1]]
                for x in np.stack((time_slice_offset, values_slice), axis=1)
            ]
            # Not allowed to have a timeseries of length 1, append timestep after 15 min
            if len(values) == 1:
                values.append([values[0][0] + 15 * 60, 0.0])

            rain_data = {
                "offset": time_slice[0],
                "interpolate": False,
                "values": values,
                "units": "m/s",
            }
            api_call(
                api.simulations_events_rain_timeseries_create,
                simulation.id,
                **{"data": rain_data},
            )

        rain_event_simulations.append(simulation)
        api_call(
            api.simulations_actions_create,
            *(
                simulation.id,
                Action(name="queue"),
            ),
        )

    for warning in warnings:
        print(warning)

    return rain_event_simulations


def create_result_file(
    threedimodel_id: int,
    simulation_dwf: Simulation,
    rain_event_simulations: List[Simulation],
    saved_states: List[SavedStateOverview],
    results_dir: Path,
) -> None:
    data = {
        "threedimodel_id": threedimodel_id,
        "simulation_dwf": simulation_dwf.to_dict(),
        "rain_event_simulations": [re.to_dict() for re in rain_event_simulations],
        "saved_states": [ss.to_dict() for ss in saved_states],
    }
    results_file = Path(
        results_dir, f"created_simulations_{datetime.now().strftime('%Y-%m-%d')}.json"
    )
    with results_file.open("w") as f:
        json.dump(data, f, indent=4, default=str)
        print(f"Writing output to {results_file}")


@click.command()
@click.argument(
    "threedimodel_id",
    type=int,
)
@click.argument(
    "rain_files_dir",
    type=click.Path(exists=True, readable=True, path_type=Path),
)
@click.argument(
    "results_dir",
    type=click.Path(exists=True, writable=True, path_type=Path),
)
@click.argument(
    "user",
    type=str,
)
@click.option(
    "-o",
    "--organisation",
    type=str,
    default="4178c71845f14a3babc1b042e7505193",
    help="Organisation unique id",
)
@click.option(
    "-h",
    "--host",
    type=str,
    default="https://api.3di.live",
    help="Host to run batch calculation on",
)
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
)
def create_rain_series_simulations(
    threedimodel_id: int,
    rain_files_dir: Path,
    results_dir: Path,
    user: str,
    password: str,
    organisation: str,
    host: str,
):
    """
    \b
    Batch rain series calculation consists of 2 parts.
    First part:
        - run simulation in dry state for 3 days
        - create saved states for every hour in day 3 which will be used as start state for the rain series simulations

    \b
    Second part:
        - start individual simulations which take a rain event as input
        - the filename contains information about the start date and time of the event
    """
    config = {
        "THREEDI_API_HOST": host,
        "THREEDI_API_USERNAME": user,
        "THREEDI_API_PASSWORD": password,
    }
    with ThreediApi(config=config, version="v3-beta") as api:
        api: V3BetaApi
        sqlite_path = download_sqlite(api, threedimodel_id, results_dir)
        validate_sqlite(sqlite_path)

        # Setup simulation and in dry state to create saved states
        print("Creating 3 day DWF simulation")
        simulation_dwf: Simulation = create_simulation(
            api,
            threedimodel_id,
            organisation,
            3 * 24 * 60 * 60,
            RAIN_EVENTS_START_DATE.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        saved_states = create_saved_states(api, simulation_dwf)
        api_call(
            api.simulations_actions_create,
            *(
                simulation_dwf.id,
                Action(name="queue"),
            ),
        )
        await_simulation_completion(api, simulation_dwf)

        # Convenience functions in case DWF simulation is already available
        # simulation_dwf = api.simulations_read(22487)
        # saved_states = get_saved_states(api, simulation_dwf)

        # create netcdf files from rain timeseries and create simulations
        # netcdfs = convert_to_netcdf(rain_files_dir)
        # rain_event_simulations = create_simulations_from_netcdf_rain_events(
        #     api,
        #     saved_states,
        #     netcdfs,
        #     threedimodel_id,
        #     organisation,
        # )

        rain_event_simulations = create_simulations_from_rain_events(
            api, saved_states, threedimodel_id, organisation, rain_files_dir
        )

        # write results to out_path
        create_result_file(
            threedimodel_id,
            simulation_dwf,
            rain_event_simulations,
            saved_states,
            results_dir,
        )


if __name__ == "__main__":
    create_rain_series_simulations()
