import asyncio
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal, List, Dict, Callable

import numpy as np
import urllib3
import websockets
from openapi_client import ApiException
from threedi_api_client.files import download_file
from threedi_api_client.openapi import Simulation
from threedi_api_client.openapi.api.v3_api import V3Api
from threedigrid.admin.gridadmin import GridH5Admin

DOWNLOAD_TIMEOUT = urllib3.Timeout(connect=60, read=600)

@dataclass
class MeasureLocation:
    code: str
    name: str
    connection_node_id: int
    node_id: Optional[int] = None
    water_levels: Optional[List[float]] = field(default_factory=list)

    def get_node_id(self, gridadmin_path):
        ga = GridH5Admin(gridadmin_path)
        node = ga.nodes.connectionnodes.filter(content_pk__eq=self.connection_node_id)
        self.node_id = int(node.id[0])

    @property
    def is_rising(self):
        if len(self.water_levels) < 2:
            return False
        else:
            return (self.water_levels[-1]) > (self.water_levels[-2])

    @property
    def is_falling(self):
        if len(self.water_levels) < 2:
            return False
        else:
            return (self.water_levels[-1]) < (self.water_levels[-2])

    def is_below_last_peak(self, threshold: float) -> bool:
        """
        Check if the last water level value is at least `threshold` below the last peak.

        Parameters
        ----------
        threshold : float
            Amount the last value must be below the last peak.

        Returns
        -------
        bool
            True if last value is at least `threshold` below the last peak, else False.
        """
        levels = np.array(self.water_levels)
        n = len(levels)
        if n < 3:
            return False  # need at least 3 points to have a peak

        # find indices of peaks: higher than both neighbors
        peak_indices = [i for i in range(1, n - 1) if levels[i] > levels[i - 1] and levels[i] > levels[i + 1]]
        if not peak_indices:
            return False  # no peak found

        # last peak
        last_peak_value = levels[peak_indices[-1]]

        return (last_peak_value - levels[-1]) >= threshold


@dataclass
class Structure:
    type: Literal["orifice", "weir"]
    id: int
    code: str
    name: str
    discharge_coefficients: Optional[List[float]]
    is_open: bool = True

    def set_valve(
        self,
        api_client: V3Api,
        simulation: Simulation,
        action: Literal["open", "close"],
        offset: int,
        duration: int,
        max_retries: int = 900,
        wait_time: float = 1,
    ):
        """
        Open or close the structure using a timed control.
        Will not open it if it is already open / close if already closed.
        """
        if action not in ["open", "close"]:
            raise ValueError('action must be one of ["open", "close"]')
        if (action == "open" and self.is_open) or (action == "close" and not self.is_open):
            return
        value = self.discharge_coefficients if action == "open" else [0, 0]
        structure_control = api_client.simulations_events_structure_control_timed_create(
            simulation_pk=simulation.id,
            data={
                "offset": offset,
                "duration": duration,
                "value": value,
                "type": "set_discharge_coefficients",
                "structure_id": self.id,
                "structure_type": f"v2_{self.type}"
            }
        )
        structure_control_id = structure_control.id
        for i in range(max_retries):
            structure_control = api_client.simulations_events_structure_control_timed_read(
                simulation_pk=simulation.id,
                id=structure_control_id,
            )
            match structure_control.state:
                case "processing":
                    time.sleep(wait_time)
                case "valid":
                    print("Finished processing timed control")
                    self.is_open = action == "open"
                    return
                case "invalid":
                    raise Exception(
                        f"Something went wrong while processing timed control {structure_control_id}. "
                        f"State: {structure_control.state}. "
                        f"State detail: {structure_control.state_detail}"
                    )
        raise Exception(
            f"After {max_retries} retries and wait time of {wait_time} seconds, "
            f"structure control actions was still not processed"
        )


def download_gridadmin(simulation: Simulation, api_client: V3Api) -> Path:
    download_folder = Path(tempfile.mkdtemp())
    download_url = api_client.threedimodels_gridadmin_download(simulation.threedimodel_id)
    file_path = download_folder / "gridadmin.h5"
    download_file(download_url.get_url, file_path, timeout=DOWNLOAD_TIMEOUT)
    return file_path

async def read_websocket_data(
        api_client: V3Api,
        simulation_id: int,
        start_time: int,
        node_id: int
):
    water_level_websocket_url = api_client.simulations_visualisations_water_level_graph_create(
        simulation_pk=simulation_id,
        data={"start_time": start_time, "subscribe": False, "node_id": node_id}
    )
    connection_success = False
    async with websockets.connect(water_level_websocket_url.url) as websocket:
        connection_success = True
        water_level = -9999
        async for message in websocket:
            data = np.frombuffer(message, dtype=np.float32)
            water_level = data[-1]
        return water_level if ~np.isnan(water_level) else -9999
    if not connection_success:
        raise RuntimeError("Could not connect to websocket")


def read_water_level(api_client: V3Api, simulation_id: int, start_time: int, node_id: int):
    """
    Sync wrapper around async read_websocket_data function
    """
    water_level = asyncio.run(
        read_websocket_data(
            api_client=api_client,
            simulation_id=simulation_id,
            start_time=start_time,
            node_id=node_id,
        )
    )
    return water_level


def simulate_with_complex_structure_control(
        api_client: V3Api,
        simulation: Simulation,
        measure_locations: Dict,
        structures: Dict,
        measure_frequency,
        structure_control_logic: Callable[
            [V3Api, Simulation, int, Dict[str, Structure], Dict[str, MeasureLocation]],
            None
        ]

):
    """
    Run a simulation that is paused every `measure_frequency` seconds to evaluate `structure_control_logic`.

    Signature of `structure_control_logic`:

        structure_control_logic(
            api_client: V3Api,
            simulation: Simulation,
            simulation_current_time: int,
            structures: Dict[str, Structure],
            measure_locations: Dict[str, MeasureLocation],
        )

    Sets output time step to the measure frequency, because the water levels are read from the NetCDF during
    the simulation.
    """
    # Set output time step to the measure frequency, because the water levels are read from the NetCDF during
    # the simulation
    api_client.simulations_settings_output_settings_partial_update(
        simulation.id,
        {"hydro_output_time_step": measure_frequency}
    )

    gridadmin_path = download_gridadmin(api_client=api_client, simulation=simulation)
    for measure_location in measure_locations.values():
        measure_location.get_node_id(gridadmin_path)

    status = api_client.simulations_status_list(simulation_pk=simulation.id)
    while status.name not in ["ended", "postprocessing", "finished", "crashed"]:

        api_client.simulations_actions_create(
            simulation_pk=simulation.id, data={
                "name": "start",
                "duration": measure_frequency
            }
        )
        status = api_client.simulations_status_list(simulation_pk=simulation.id)
        while status.paused:
            # Wait for the simulation to resume
            time.sleep(0.1)
            status = api_client.simulations_status_list(simulation_pk=simulation.id)
        # TODO: dit kan ws. slimmer met een status websocket
        status = api_client.simulations_status_list(simulation_pk=simulation.id)
        while not (status.paused or status.name in ["ended", "postprocessing", "finished", "crashed"]):
            time.sleep(1)
            status = api_client.simulations_status_list(simulation_pk=simulation.id)

        if status.name == "initialized":
            # read water levels
            for name in measure_locations.keys():
                measure_location = measure_locations[name]
                try:
                    water_level = read_water_level(
                        api_client=api_client,
                        simulation_id=simulation.id,
                        start_time=int(status.time) - measure_frequency,  # only works while the simulation is paused
                        node_id=measure_location.node_id
                    )
                except ApiException:
                    status = api_client.simulations_status_list(simulation_pk=simulation.id)
                    if status.name in ["ended", "postprocessing", "finished", "crashed"]:
                        return
                    else:
                        raise
                measure_location.water_levels.append(water_level)

            # perform calculations to decide what needs to be done with the orifices
            # # Note that water level is -9999 if node is dry
            structure_control_logic(api_client, simulation, status.time, structures, measure_locations)


def multiple_simulate_with_complex_structure_control(
        api_client: V3Api,
        simulations: List[Simulation],
        measure_locations: Dict,
        structures: Dict,
        measure_frequency,
        structure_control_logic: Callable[
            [V3Api, Simulation, int, Dict[str, Structure], Dict[str, MeasureLocation]],
            None
        ]

):
    """
    Run a simulation that is paused every `measure_frequency` seconds to evaluate `structure_control_logic`.

    Signature of `structure_control_logic`:

        structure_control_logic(
            api_client: V3Api,
            simulation: Simulation,
            simulation_current_time: int,
            structures: Dict[str, Structure],
            measure_locations: Dict[str, MeasureLocation],
        )

    Sets output time step to the measure frequency, because the water levels are read from the NetCDF during
    the simulation.

    Assumes that all simulations use the same model.

    """
    # Set output time step to the measure frequency, because the water levels are read from the NetCDF during
    # the simulation
    gridadmin_path = download_gridadmin(api_client=api_client, simulation=simulations[0])
    for measure_location in measure_locations.values():
        measure_location.get_node_id(gridadmin_path)

    for simulation in simulations:
        api_client.simulations_settings_output_settings_partial_update(
            simulation.id,
            {"hydro_output_time_step": measure_frequency}
        )

    queued_simulations = simulations
    running_simulations = []
    session_limit = api_client.contracts_list(organisation__id==simulations[0].organisation)
    while len(queued_simulations) > 0:
    for simulation in simulations:
        status = api_client.simulations_status_list(simulation_pk=simulation.id)
        while status.name not in ["ended", "postprocessing", "finished", "crashed"]:

            api_client.simulations_actions_create(
                simulation_pk=simulation.id, data={
                    "name": "start",
                    "duration": measure_frequency
                }
            )
            status = api_client.simulations_status_list(simulation_pk=simulation.id)
            while status.paused:
                # Wait for the simulation to resume
                time.sleep(0.1)
                status = api_client.simulations_status_list(simulation_pk=simulation.id)
            # TODO: dit kan ws. slimmer met een status websocket
            status = api_client.simulations_status_list(simulation_pk=simulation.id)
            while not (status.paused or status.name in ["ended", "postprocessing", "finished", "crashed"]):
                time.sleep(1)
                status = api_client.simulations_status_list(simulation_pk=simulation.id)

            if status.name == "initialized":
                # read water levels
                for name in measure_locations.keys():
                    measure_location = measure_locations[name]
                    try:
                        water_level = read_water_level(
                            api_client=api_client,
                            simulation_id=simulation.id,
                            start_time=int(status.time) - measure_frequency,  # only works while the simulation is paused
                            node_id=measure_location.node_id
                        )
                    except ApiException:
                        status = api_client.simulations_status_list(simulation_pk=simulation.id)
                        if status.name in ["ended", "postprocessing", "finished", "crashed"]:
                            return
                        else:
                            raise
                    measure_location.water_levels.append(water_level)

                # perform calculations to decide what needs to be done with the orifices
                # # Note that water level is -9999 if node is dry
                structure_control_logic(api_client, simulation, status.time, structures, measure_locations)

