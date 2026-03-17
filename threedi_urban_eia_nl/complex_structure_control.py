import asyncio
import logging
import tempfile
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Optional, Literal, List, Dict, Callable, Tuple

import numpy as np
import urllib3
import websockets

from threedi_api_client.files import download_file
from threedi_api_client.openapi import Simulation, ApiException
from threedi_api_client.openapi.api.v3_api import V3Api
from threedigrid.admin.gridadmin import GridH5Admin

DOWNLOAD_TIMEOUT = urllib3.Timeout(connect=60, read=600)


@dataclass
class MeasureLocation:
    code: str
    name: str
    connection_node_id: int
    node_id: Optional[int] = None
    water_levels: Optional[List[List[float]]] = field(default_factory=list)

    def get_node_id(self, gridadmin_path):
        ga = GridH5Admin(gridadmin_path)
        node = ga.nodes.connectionnodes.filter(content_pk__eq=self.connection_node_id)
        self.node_id = int(node.id[0])

    @property
    def is_rising(self):
        if len(self.water_levels) < 2:
            return False
        else:
            return (self.water_levels[-1][-1]) > (self.water_levels[-2][-1])

    @property
    def is_falling(self):
        if len(self.water_levels) < 2:
            return False
        else:
            return (self.water_levels[-1][-1]) < (self.water_levels[-2][-1])

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
        levels = np.array(self.water_levels)[:, -1]

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

    def close_valve(
        self,
        api_client: V3Api,
        simulation: Simulation,
        offset: int,
        duration: int,
        max_retries: int = 900,
        wait_time: float = 1,
    ):
        """
        Open or close the structure using a timed control.
        The idea is that it is used for a single measure_frequency time step
        """
        structure_control = api_client.simulations_events_structure_control_timed_create(
            simulation_pk=simulation.id,
            data={
                "offset": offset,
                "duration": duration,
                "value": [0, 0],
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
                    self.is_open = False
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

    def open_valve(self):
        """
        Update the administration of this structure.
        Does not affect any timed controls, as the idea is that close actions are valid for a single `measure_frequency`
         time step only
        """
        self.is_open = True


class SimulationManager:
    """Object that manages a simulation client-side to implement complex structure control"""

    def __init__(
        self,
        parent: 'QueueManager',
        api_client: V3Api,
        simulation: Simulation,
        structures: Dict[str, Structure],
        measure_locations: Dict[str, MeasureLocation],
        measure_frequency: int,
        structure_control_logic: Callable[
            [V3Api, Simulation, int, Dict[str, Structure], Dict[str, MeasureLocation], float, Optional[logging.Logger]],
            None
        ],
        log_dir: Path | None = None,
    ):

        self.parent = parent
        self.api_client = api_client
        self.simulation = simulation
        self.structures = structures
        self.measure_locations = measure_locations
        self.measure_frequency = measure_frequency
        self.structure_control_logic = structure_control_logic

        # Create a unique logger for this instance
        self.logger = logging.getLogger(f"Simulation.{simulation.id}_{simulation.name}")
        self.logger.setLevel(logging.DEBUG)

        # Prevent double handlers if multiple instances are created
        if not self.logger.handlers:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"{simulation.id}_{simulation.name}_{timestamp}.log"
            log_path = log_dir / log_filename if log_dir else Path(log_filename)
            handler = logging.FileHandler(log_path)
            handler.setLevel(logging.DEBUG)

            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)

            self.logger.addHandler(handler)

    def resume(self):
        """Starts or resumes the simulation. Informs the queue manager if simulation is finished"""
        status = self.api_client.simulations_status_list(simulation_pk=self.simulation.id)
        if status.name in ["finished", "crashed"]:
            self.parent.finish(self.simulation.id)
        elif status.name == "initialized":
            if status.paused:  # if simulation is initialized and not paused, it is just running
                print(
                    f"Resuming simulation {self.simulation.id} "
                    f"at {status.time} seconds, {int(status.time / self.simulation.duration * 100)} % ..."
                )
                time_before_resuming = status.time
                try:
                    self.api_client.simulations_actions_create(
                        simulation_pk=self.simulation.id,
                        data={
                            "name": "start",
                            "duration": self.measure_frequency
                        }
                    )
                except ApiException as e:
                    if e.status == 400:
                        print("Something fishy is going on, let's wait a bit and try again. Exception:")
                        print(repr(e))
                    else:
                        raise e
                total_waited = 0
                while (
                    total_waited < 60 and
                    status.name == "initialized" and
                    status.paused and
                    status.time == time_before_resuming
                ):
                    # Wait for the simulation to resume
                    sleep_time = 0.1
                    time.sleep(sleep_time)
                    total_waited += sleep_time
                    status = self.api_client.simulations_status_list(simulation_pk=self.simulation.id)
        elif status.name in ["created"]:
            try:
                self.api_client.simulations_actions_create(
                    simulation_pk=self.simulation.id, data={
                        "name": "start",
                        "duration": self.measure_frequency
                    }
                )
            except ApiException:
                # assuming this is because there are no sessions available
                # we will try again next round
                print(
                    f"Simulation {self.simulation.id} cannot be started, probably there are no sessions available."
                    "Will try again later."
                )
        elif status.name in ["starting", "queued", "ended", "postprocessing"]:
            pass  # just wait for the status to become one of the others that we can deal with
        else:
            raise RuntimeError(f"Simulation {self.simulation.id} has unknown status '{status.name}'")

    def finish(self):
        self.logger.info("Water levels read during simulation:")
        for measure_location_name, measure_location in self.measure_locations.items():
            self.logger.info(f"Measure location {measure_location_name}")
            self.logger.info(str(measure_location.water_levels))

    def read_water_levels(self, current_simulation_time: float):
        """
        Read water level for each measure location and append it to that measure location's .water_levels attribute
        """
        for name in self.measure_locations.keys():
            measure_location = self.measure_locations[name]
            try:
                time_step, water_level = read_water_level(
                    api_client=self.api_client,
                    simulation_id=self.simulation.id,
                    start_time=current_simulation_time - self.measure_frequency,  # only works while the simulation is paused
                    node_id=measure_location.node_id
                )
            except ApiException:
                status = self.api_client.simulations_status_list(simulation_pk=self.simulation.id)
                if status.name in ["ended", "postprocessing", "finished", "crashed"]:
                    return
                else:
                    raise
            measure_location.water_levels.append([time_step, water_level])

    def apply_structure_control_logic(self):
        wait_times = [1, 2, 5, 10, 20, 60, -9999]  # last wait time will be ignored
        for wait in wait_times:
            try:
                status = self.api_client.simulations_status_list(simulation_pk=self.simulation.id)
            except ApiException as e:
                if e.status == 502 and wait != wait_times[-1]:  # 502 = Bad gateway
                    time.sleep(wait)
                    continue
                else:
                    raise e

        if status.name in ["finished", "crashed"]:
            self.parent.finish(self.simulation.id)
        elif status.name == "initialized":
            if status.paused:
                self.read_water_levels(status.time)
                self.structure_control_logic(
                    self.api_client,
                    self.simulation,
                    status.time,
                    self.structures,
                    self.measure_locations,
                    self.measure_frequency,
                    self.logger,
                )
            else:
                pass  # just wait until the next round
        elif status.name in ["created", "starting", "queued", "ended", "postprocessing"]:
            pass  # just wait for the status to become one of the others that we can deal with


class QueueManager:
    """Manages a queue of simulations that have the same set of structures and measure locations"""
    def __init__(
            self,
            api_client: V3Api,
            structures: Dict[str, Structure],
            measure_locations: Dict[str, MeasureLocation],
            measure_frequency: int,
            structure_control_logic: Callable[
                [V3Api, Simulation, int, Dict[str, Structure], Dict[str, MeasureLocation], float, Optional[logging.Logger]],
                None
            ],
            log_dir: Path | None = None
    ):
        self.api_client = api_client
        self.queued_simulations: List[Simulation] = []
        self._running_simulations: Dict[int, SimulationManager] = {}
        self.finished_simulations: List[Simulation] = []
        self.structures = structures
        self.measure_locations = measure_locations
        self.measure_frequency = measure_frequency
        self.structure_control_logic = structure_control_logic
        self.log_dir = log_dir

    @property
    def running_simulations(self) -> Dict[int, SimulationManager]:
        return self._running_simulations

    def fill_running(self):
        """Add simulations to running simulations until nr of running simulations equals organisations' session limit"""
        if len(self.running_simulations) == 0:
            self.run_next()
        a_running_simulation = next(iter(self._running_simulations.values()))
        organisation = a_running_simulation.simulation.organisation
        session_limit = self.api_client.contracts_list(
            organisation__unique_id=organisation
        ).results[0].session_limit
        for _ in range(min(session_limit - len(self._running_simulations), len(self.queued_simulations))):
            self.run_next()

    def run_next(self) -> bool:
        """
        Pop the first simulation from the queue, create a simulation manager for it and add that to running simulations.
        Returns False if no simulation was available in the queue
        """
        if len(self.queued_simulations) > 0:
            simulation = self.queued_simulations.pop(0)
            simulation_manager = SimulationManager(
                parent=self,
                api_client=self.api_client,
                simulation=simulation,
                structures=deepcopy(self.structures),
                measure_locations=deepcopy(self.measure_locations),
                measure_frequency=self.measure_frequency,
                structure_control_logic=self.structure_control_logic,
                log_dir=self.log_dir,
            )
            self._running_simulations[simulation.id] = simulation_manager
            simulation_manager.logger.info(f"Added simulation {simulation.id} to running simulations")
            return True
        else:
            return False

    def finish(self, simulation_id: int):
        """
        Moves simulation with given simulation id from running simulations to finished simulations
        Calls run_next after that
        Raises IndexError if given simulation was not in running simulations
        """
        simulation_manager = self._running_simulations.pop(simulation_id)
        simulation_manager.finish()
        self.finished_simulations.append(simulation_manager.simulation)
        print(f"Finished simulation {simulation_manager.simulation.id}")
        self.run_next()

    def resume_running_simulations(self):
        # use list() to materialize the current values so the loop won’t break if the dict is modified inside the loop
        # simulations started during this iteration are processed next time
        for simulation_manager in list(self.running_simulations.values()):
            simulation_manager.resume()

    def apply_structure_control_logic(self):
        # use list() to materialize the current values so the loop won’t break if the dict is modified inside the loop
        # simulations started during this iteration are processed next time
        for simulation_manager in list(self.running_simulations.values()):
            simulation_manager.apply_structure_control_logic()


def retry_on_500(delays=(0.1, 1, 2, 5, 10, 20, 50, 60)):
    """
    Retry decorator that retries when an ApiException with status=500 occurs.
    Retries after the specified delays; raises after final attempt.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i, delay in enumerate(delays):
                try:
                    return func(*args, **kwargs)
                except ApiException as e:
                    # only retry on status 500
                    if getattr(e, "status", None) == 500:
                        if i == len(delays) - 1:
                            # last attempt -> re-raise
                            raise
                        print(f"ApiException (500) encountered. Trying again in {delay} seconds")
                        time.sleep(delay)
                    else:
                        # other errors should not be retried
                        raise
        return wrapper
    return decorator


def download_gridadmin(simulation: Simulation, api_client: V3Api) -> Path:
    download_folder = Path(tempfile.mkdtemp())
    download_url = api_client.threedimodels_gridadmin_download(simulation.threedimodel_id)
    file_path = download_folder / "gridadmin.h5"
    download_file(download_url.get_url, file_path, timeout=DOWNLOAD_TIMEOUT)
    return file_path


async def read_websocket_data(
        api_client: V3Api,
        simulation_id: int,
        start_time: float,
        node_id: int
) -> Tuple[float, float]:
    water_level_websocket_url = api_client.simulations_visualisations_water_level_graph_create(
        simulation_pk=simulation_id,
        data={"start_time": start_time, "subscribe": False, "node_id": node_id}
    )
    connection_success = False
    async with websockets.connect(water_level_websocket_url.url) as websocket:
        connection_success = True
        water_level = -9999.0
        async for message in websocket:
            data = np.frombuffer(message, dtype=np.float32)
            time_step = data[-2]
            water_level = data[-1]
        water_level = -9999.0 if np.isnan(water_level) else water_level
        return time_step, water_level
    if not connection_success:
        raise RuntimeError("Could not connect to websocket")


@retry_on_500()
def read_water_level(api_client: V3Api, simulation_id: int, start_time: float, node_id: int) -> Tuple[float, float]:
    """
    Sync wrapper around async read_websocket_data function
    """
    time_step, water_level = asyncio.run(
        read_websocket_data(
            api_client=api_client,
            simulation_id=simulation_id,
            start_time=start_time,
            node_id=node_id,
        )
    )
    return time_step, water_level


def simulate_with_complex_structure_control(
        api_client: V3Api,
        simulation: Simulation,
        measure_locations: Dict,
        structures: Dict,
        measure_frequency,
        structure_control_logic: Callable[
            [V3Api, Simulation, int, Dict[str, Structure], Dict[str, MeasureLocation], float, Optional[logging.Logger]],
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
                    time_step, water_level = read_water_level(
                        api_client=api_client,
                        simulation_id=simulation.id,
                        start_time=status.time - measure_frequency,  # only works while the simulation is paused
                        node_id=measure_location.node_id
                    )
                except ApiException:
                    status = api_client.simulations_status_list(simulation_pk=simulation.id)
                    if status.name in ["ended", "postprocessing", "finished", "crashed"]:
                        return
                    else:
                        raise
                measure_location.water_levels.append([time_step, water_level])

            # perform calculations to decide what needs to be done with the orifices
            # # Note that water level is -9999 if node is dry
            structure_control_logic(
                api_client,
                simulation,
                status.time,
                structures,
                measure_locations,
                measure_frequency,
                None
            )


def multiple_simulate_with_complex_structure_control(
        api_client: V3Api,
        simulations: List[Simulation],
        measure_locations: Dict,
        structures: Dict,
        measure_frequency,
        structure_control_logic: Callable[
            [V3Api, Simulation, int, Dict[str, Structure], Dict[str, MeasureLocation], float, Optional[logging.Logger]],
            None
        ],
        log_dir: Path | None = None
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
    Assumes that organisation is used for this purpose only (no other simulations are being queued)
    """
    # Get node ids for measure locations
    gridadmin_path = download_gridadmin(api_client=api_client, simulation=simulations[0])
    for measure_location in measure_locations.values():
        measure_location.get_node_id(gridadmin_path)

    # Set output time step to the measure frequency, because the water levels are read from the NetCDF during
    # the simulation
    for simulation in simulations:
        api_client.simulations_settings_output_settings_partial_update(
            simulation.id,
            {"hydro_output_time_step": measure_frequency}
        )

    # Run it all
    queue_manager = QueueManager(
        api_client=api_client,
        measure_frequency=measure_frequency,
        measure_locations=measure_locations,
        structures=structures,
        structure_control_logic=structure_control_logic,
        log_dir=log_dir,
    )
    queue_manager.queued_simulations = simulations
    queue_manager.fill_running()

    while len(queue_manager.running_simulations) > 0:
        queue_manager.resume_running_simulations()
        time.sleep(1)
        queue_manager.apply_structure_control_logic()
        while queue_manager.finished_simulations:
            yield queue_manager.finished_simulations.pop()
