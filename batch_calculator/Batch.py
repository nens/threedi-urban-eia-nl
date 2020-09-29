import os

from openapi_client.api import ThreedimodelsApi
from batch_calculator.read_rainfall_events import RainEventReader
from batch_calculator.AddDWF import read_dwf_per_node
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
        results_dir,
        ini_2d_water_level_constant=None,
        ini_2d_water_level_raster_url=None,
        sqlite_path=None,
        saved_state_url=None,
    ):
        self._client = client
        self._threedi_models = ThreedimodelsApi(client)

        self.rain_files_dir = rain_files_dir
        self.sqlite_path = sqlite_path
        self.model_id = model_id
        self.model_name = model_name
        self.org_id = org_id
        self.ini_2d_water_level_constant = ini_2d_water_level_constant
        self.ini_2d_water_level_raster_url = ini_2d_water_level_raster_url
        self.results_dir = results_dir
        self.saved_state_url = saved_state_url

        # Add initial 2d water level raster if available
        if (
            self._threedi_models.threedimodels_initial_waterlevels_list(
                self.model_id
            ).count
            == 1
        ):
            self.ini_2d_water_level_raster_url = (
                self._threedi_models.threedimodels_initial_waterlevels_list(
                    self.model_id
                )
                .results[0]
                .url
            )

        # Get total amount of dry weather flow per node per 24h if sqlite is given
        dwf_per_node_24h = None
        if self.sqlite_path is not None:
            dwf_per_node_24h = read_dwf_per_node(self.sqlite_path)

        # "https://api.3di.live/v3.0/threedimodels/7101/initial_waterlevels/476/"

        for filename in os.listdir(self.rain_files_dir):
            rain_file_path = os.path.join(self.rain_files_dir, filename)

            rain_event = RainEventReader(rain_file_path)

            sim = StartSimulation(
                self._client,
                self.model_id,
                self.model_name,
                self.org_id,
                rain_event.duration,
                rain_event,
                dwf_per_node_24h,
                self.ini_2d_water_level_constant,
                self.ini_2d_water_level_raster_url,
                self.saved_state_url,
                start_datetime=rain_event.start_datetime,
            )

            results = DownloadResults(
                self._client, sim.created_sim_id, sim.model_id, self.results_dir
            )

        self.agg_dir = results.agg_dir
