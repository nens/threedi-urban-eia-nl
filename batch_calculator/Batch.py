import os

# from openapi_client.api import ThreedimodelsApi
from batch_calculator.read_rainfall_events import RainEventReader
from batch_calculator.StartSimulation import StartSimulation
from batch_calculator.DownloadResults import DownloadResults


class Batch:
    def __init__(
        self,
        rain_files_dir,
        client,
        model_id,
        model_name,
        org_id,
        ini_2d_water_level,
        results_dir,
        saved_state_url=None,
    ):
        self._client = client
        # self._threedi_models = ThreedimodelsApi(client)

        self.rain_files_dir = rain_files_dir
        self.model_id = model_id
        self.model_name = model_name
        self.org_id = org_id
        self.ini_2d_water_level = ini_2d_water_level
        self.results_dir = results_dir
        self.saved_state_url = saved_state_url

        for filename in os.listdir(self.rain_files_dir):
            rain_file_path = os.path.join(self.rain_files_dir, filename)

            rain_event = RainEventReader(rain_file_path)

            # bui.get_timeseries()

            sim = StartSimulation(
                self._client,
                self.model_id,
                self.model_name,
                self.org_id,
                rain_event.duration,
                rain_event,
                self.ini_2d_water_level,
                self.saved_state_url,
                start_datetime=rain_event.start_datetime,
            )

            results = DownloadResults(
                self._client, sim.created_sim_id, sim.model_id, self.results_dir
            )

        self.agg_dir = results.agg_dir
