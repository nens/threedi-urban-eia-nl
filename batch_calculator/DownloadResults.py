import os
import requests

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
        self.agg_dir = self.output_dir + "/" + "aggregation_netcdfs"

        sim_results = self._sims.simulations_results_files_list(self.sim_id).results
        result_dir = self.output_dir + "/" + "simulation-" + str(self.sim_id)

        if not os.path.exists(result_dir):
            os.mkdir(result_dir)

        if not os.path.exists(self.agg_dir):
            os.mkdir(self.agg_dir)

        if not os.path.exists("gridadmin.h5"):
            gridadmin = self._threedi_models.threedimodels_gridadmin_download(
                self.model_id, async_req=False
            )
            self.write_file_from_url(
                gridadmin.get_url, self.agg_dir + "/" + "gridadmin.h5"
            )

        for result in sim_results:
            download = self._sims.simulations_results_files_download(
                result.id, self.sim_id
            )
            if result.filename.startswith("agg"):
                self.write_file_from_url(
                    download.get_url,
                    self.agg_dir + "/" + self.append_id(result.filename),
                )
                print("Downloaded: ", result.filename)
            else:
                self.write_file_from_url(
                    download.get_url,
                    result_dir
                    + "/"
                    + self.append_id(result.filename),  # + '_sim-' + str(self.sim_id)
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

    # def get_agg_dir(self):

    #     return self.agg_dir
