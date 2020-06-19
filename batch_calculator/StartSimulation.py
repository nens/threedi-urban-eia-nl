import time

from openapi_client import SimulationsApi
from openapi_client.models.simulation import Simulation


class StartSimulation:
    def __init__(
        self,
        client,
        model_id,
        model_name,
        organisation_id,
        duration,
        rain_event,
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

        # Add initial saved state
        # self._sim.simulations_initial_saved_state_create(
        #     self.created_sim_id, {"saved_state": self.saved_state_url},
        # )

        # Create a rain timeseries
        self._sim.simulations_events_rain_timeseries_create(
            self.created_sim_id, rain_event.rain_data
        )

        # Create a timed save state at the end of the simulation duration
        # OP HET MOMENT WERKT DWF NOG NIET, DUS VOORLOPIG OVERSLAAN
        self._sim.simulations_create_saved_states_timed_create(
            self.created_sim_id,
            {
                "name": "saved_state_sim" + str(self.created_sim_id),
                "time": rain_event.duration,
            },
        )

        # Add global 2D waterlevel
        self._sim.simulations_initial2d_water_level_constant_create(
            self.created_sim_id,
            {
                "value": 5.1
            },
        )

        # Start the simulation with id = created_sim_id
        self._sim.simulations_actions_create(  # TODO sim_start =
            simulation_pk=self.created_sim_id, data={"name": "start"}
        )

        status = self._sim.simulations_status_list(self.created_sim_id, async_req=False)
        print(status.name, end="\r", flush=True)
        while status.name == "starting":
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
        print(progress.percentage)
        while progress.percentage < 100:
            progress = self._sim.simulations_progress_list(
                self.created_sim_id, async_req=False
            )
            print(progress.percentage, end="\r", flush=True)
            time.sleep(1.0)

        # Check saved state upload
        # print(self._sim.simulations_create_saved_states_timed_list(self.created_sim_id))

        # TODO met bedrijf delen, en testen
