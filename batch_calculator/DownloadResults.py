import os
import requests
import time

from openapi_client import SimulationsApi
from openapi_client.api import ThreedimodelsApi


class DownloadResults:
    def __init__(self, client, sim_id, model_id, output_dir):
        self._client = client
        self._sims = SimulationsApi(client)
        self._threedi_models = ThreedimodelsApi(client)

        self.sim_id = sim_id
        self.model_id = model_id
        self.output_dir = output_dir
        self.agg_dir = os.path.join(self.output_dir, "aggregation_netcdfs")

        result_dir = os.path.join(self.output_dir, "simulation-" + str(self.sim_id))

        # Create directories that will store results and aggregation results if they do not exist yet
        if not os.path.exists(result_dir):
            os.mkdir(result_dir)

        if not os.path.exists(self.agg_dir):
            os.mkdir(self.agg_dir)

        # Download gridadmin.h5
        if not os.path.exists(os.path.join(self.agg_dir, "gridadmin.h5")):
            gridadmin = self._threedi_models.threedimodels_gridadmin_download(
                self.model_id, async_req=False
            )
            self.write_file_from_url(
                gridadmin.get_url, os.path.join(self.agg_dir, "gridadmin.h5")
            )
            print("Created new gridadmin.h5")

        # Wait with downloading simulation-specific results until the simulation status is "finished"
        while (
            self._sims.simulations_status_list(self.sim_id, async_req=False)
            != "finished"
        ):
            time.sleep(5.0)
            print("waiting for simulation status to be set to 'finished'...")

        # Create variable that contains the simulation results
        sim_results = self._sims.simulations_results_files_list(self.sim_id).results

        # Double check whether the results have been uploaded
        while sim_results == [] or (
            sim_results[0].file.state != "uploaded"
            or sim_results[1].file.state != "uploaded"
            or sim_results[2].file.state != "uploaded"
        ):
            sim_results = self._sims.simulations_results_files_list(self.sim_id).results
            print("Waiting for result files to be uploaded...")
            time.sleep(5.0)

        # Download aggregate results netcdf, results netcdf and logfiles
        for result in sim_results:
            download = self._sims.simulations_results_files_download(
                result.id, self.sim_id
            )
            if result.filename.startswith("agg"):
                self.write_file_from_url(
                    download.get_url,
                    os.path.join(self.agg_dir, self.append_id(result.filename)),
                )
                print("Downloaded: ", result.filename)
            else:
                self.write_file_from_url(
                    download.get_url,
                    os.path.join(result_dir, self.append_id(result.filename)),
                )
                print("Downloaded: ", result.filename)

    def write_file_from_url(self, url, filepath):
        with open(filepath, "wb") as f:
            file_data = requests.get(url)
            f.write(file_data.content)
        return

    def append_id(self, filename):
        name, ext = os.path.splitext(filename)
        return "{name}_sim_{uid}{ext}".format(name=name, uid=str(self.sim_id), ext=ext)
