import os

from batch_calculator.read_rainfall_events import BuiReader
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
        reeks=False,
    ):
        self._client = client

        self.rain_files_dir = rain_files_dir
        self.model_id = model_id
        self.model_name = model_name
        self.org_id = org_id
        self.results_dir = results_dir

        # Read all files in rain_files_dir using BuiReader()
        # Run all the rainfall events one after another with StartSimulation()
        # Write saved state at the end of simulation duration (should this func be included in StartSimulation()?)

        # if reeks:

        #     # Start simulation with only dry weather flow
        #     sim = StartSimulation(
        #         self._client, self.model_id, self.model_name, self.org_id
        #     )

        for filename in os.listdir(self.rain_files_dir):
            rain_file_path = os.path.join(self.rain_files_dir, filename)

            bui = BuiReader(rain_file_path)

            # bui.get_timeseries()

            sim = StartSimulation(
                self._client,
                self.model_id,
                self.model_name,
                self.org_id,
                bui.duration,
                bui,
                start_datetime=bui.start_datetime,
            )

            results = DownloadResults(
                self._client, sim.created_sim_id, sim.model_id, self.results_dir
            )