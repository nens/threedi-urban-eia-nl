import time
import logging

from openapi_client import SimulationsApi
from openapi_client.models.simulation import Simulation
from batch_calculator.AddDWF import generate_upload_json_for_rain_event

logger = logging.getLogger(__name__)


class StartSimulation:
    def __init__(
        self,
        client,
        model_id,
        model_name,
        organisation_id,
        duration,
        rain_event,
        dwf_per_node_24h,
        ini_2d_water_level_constant=None,
        ini_2d_water_level_raster_url=None,
        saved_state_url=None,
        start_datetime="2020-01-01T00:00:00",
    ):
        self._client = client
        self._sim = SimulationsApi(client)

        self.model_id = model_id
        self.organisation_id = organisation_id
        self.saved_state_url = saved_state_url
        self.start_datetime = start_datetime
        self.sim_name = model_name + "_" + self.start_datetime
        self.duration = duration
        self.ini_2d_water_level_constant = ini_2d_water_level_constant
        self.ini_2d_water_level_raster_url = ini_2d_water_level_raster_url
        self.dwf_per_node_24h = dwf_per_node_24h

        my_sim = Simulation(
            name=self.sim_name,
            threedimodel=self.model_id,
            organisation=self.organisation_id,
            start_datetime=self.start_datetime,
            duration=self.duration,
        )

        sim = self._sim.simulations_create(my_sim)
        self.created_sim_id = sim.id
        self.sim_id_value = str(self.created_sim_id)

        print("curr_sim_id: " + self.sim_id_value)

        # Add dry weather flow laterals
        if dwf_per_node_24h is not None:
            dwf_json = generate_upload_json_for_rain_event(
                dwf_per_node_24h, rain_event.start_time, rain_event.duration
            )
            # print("DWF JSON:")
            # print(dwf_json)
            print("Adding 1d DWF laterals...")
            for lateral in dwf_json:
                lateral_response = self._sim.simulations_events_lateral_timeseries_create(
                    self.created_sim_id, lateral
                )
                print(lateral_response)
                # while lateral_response.state_detail ==

        # Add initial saved state
        if saved_state_url is not None:
            self._sim.simulations_initial_saved_state_create(
                self.created_sim_id, {"saved_state": self.saved_state_url},
            )
            print("Using savedstate url: ", self.saved_state_url)

        # Create a rain timeseries
        self._sim.simulations_events_rain_timeseries_create(
            self.created_sim_id, rain_event.rain_data
        )

        # # Create a timed save state at the end of the simulation duration
        # self._sim.simulations_create_saved_states_timed_create(
        #     self.created_sim_id,
        #     {
        #         "name": "saved_state_sim" + str(self.created_sim_id),
        #         "time": rain_event.duration,
        #     },
        # )

        # Opties:
        # 1.    Schrijf saved state sim id naar text file zodat je id behoudt ook bij een crash
        # 2.    Met logging terugggeven

        # Add 2D waterlevel raster if available
        if self.ini_2d_water_level_raster_url is not None:
            self._sim.simulations_initial2d_water_level_raster_create(
                self.created_sim_id,
                {
                    "aggregation_method": "mean",
                    "initial_waterlevel": self.ini_2d_water_level_raster_url,
                },
            )
            print(
                "Using the following 2d waterlevel raster:",
                self.ini_2d_water_level_raster_url,
            )
        else:
            print("Couldn't find a 2d waterlevel raster")

        # Add constant global 2D waterlevel if no 2D waterlevel raster has been provided
        if (
            self.ini_2d_water_level_raster_url is None
        ):  # Removed: 'saved_state_url is None and'
            self._sim.simulations_initial2d_water_level_constant_create(
                self.created_sim_id, {"value": self.ini_2d_water_level_constant},
            )
            print(
                "Using constant 2d waterlevel of: ",
                self.ini_2d_water_level_constant,
                " mNAP",
            )

        # Add the 1D waterlevels that have been specified in v2_connection_nodes
        if saved_state_url is None:
            self._sim.simulations_initial1d_water_level_predefined_create(
                self.created_sim_id, {},
            )

        # Check if 2D waterlevel is provided
        waterlvl_2d_const = self._sim.simulations_initial2d_water_level_constant_list(
            self.created_sim_id
        )
        waterlvl_2d_raster = self._sim.simulations_initial2d_water_level_raster_list(
            self.created_sim_id
        )

        if waterlvl_2d_const.count == 0 and waterlvl_2d_raster.count == 0:
            logger.warning("No 2D waterlevel has been provided")

        # Start the simulation with id = created_sim_id
        self._sim.simulations_actions_create(  # TODO sim_start =
            simulation_pk=self.created_sim_id, data={"name": "queue"}
        )

        status = self._sim.simulations_status_list(self.created_sim_id, async_req=False)
        print(status.name, end="\r", flush=True)
        while status.name == "queued" or status.name == "starting":
            print(status.name, end="\r", flush=True)
            status = self._sim.simulations_status_list(
                self.created_sim_id, async_req=False
            )
            time.sleep(5.0)
        print(status.name)

        self._sim.simulations_progress_list(  # TODO progress =
            self.created_sim_id, async_req=False
        )

        # Required, otherwise DownloadResults tries downloading while simulation is still running
        # Sometimes gets stuck
        progress = self._sim.simulations_progress_list(
            self.created_sim_id, async_req=False
        )
        while progress.percentage < 100:
            progress = self._sim.simulations_progress_list(
                self.created_sim_id, async_req=False
            )
            print(progress.percentage, "%", end="\r", flush=True)
            time.sleep(1.0)

        # Check saved state upload
        # print(self._sim.simulations_create_saved_states_timed_list(self.created_sim_id))
