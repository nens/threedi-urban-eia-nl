import os

from openapi_client.api import ThreedimodelsApi
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
        results_dir,
        ini_2d_water_level_constant=None,
        ini_2d_water_level_raster_url=None,
        saved_state_url=None,
    ):
        self._client = client
        self._threedi_models = ThreedimodelsApi(client)

        self.rain_files_dir = rain_files_dir
        self.model_id = model_id
        self.model_name = model_name
        self.org_id = org_id
        self.ini_2d_water_level_constant = ini_2d_water_level_constant
        self.ini_2d_water_level_raster_url = ini_2d_water_level_raster_url
        self.results_dir = results_dir
        self.saved_state_url = saved_state_url

        if (
            self._threedi_models.threedimodels_rasters_list(
                self.model_id, type="initial_waterlevel_file"
            ).count
            == 1
        ):
            self.ini_2d_water_level_raster_url = (
                self._threedi_models.threedimodels_rasters_list(
                    self.model_id, type="initial_waterlevel_file"
                )
                .results[0]
                .url
            )

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
                self.ini_2d_water_level_constant,
                self.ini_2d_water_level_raster_url,
                self.saved_state_url,
                start_datetime=rain_event.start_datetime,
            )

            results = DownloadResults(
                self._client, sim.created_sim_id, sim.model_id, self.results_dir
            )

        self.agg_dir = results.agg_dir
