# installeer openapi_client pip install threedi-api-client==3.0b20

import os
from threedi_api_client import ThreediApiClient
from openapi_client.api import ThreedimodelsApi, OrganisationsApi, SimulationsApi
from openapi_client.models.simulation import Simulation
from threedi_scenario_downloader import downloader as dl
import openapi_client
import datetime
import ast
import re
import time

SCRIPT_DIR = os.path.dirname(__file__)
repository_slug = 'v2_bergermeer'
simulation_name = 'lvw_python_test'
organisation_name = 'Nelen & Schuurmans'
simulation_start_date = datetime.date.today()
simulation_start_time = '10:00:00'
simulation_duration_s = 3600
rain_timeseries = '0,0.00001944444\n3600,0'  # 70 mm /u
lizard_username = 'leendert.vanwolfswin'
lizard_password = '7D@yinalife7'
srs = "EPSG:28992"
raster_resolution = 0.5
out_dir = 'C:/Users/leendert.vanwolfswin/Downloads'


def parse_rain_timeseries(ts, offset=0):
    rain_data = {
        "offset": 0,
        "interpolate": False,
        "values": [[0]],
        "units": "m/s"
    }
    rain_data.update(offset=int(offset))
    timeseries = [list(ast.literal_eval(item)) for item in ts.split('\n')]
    rain_data.update(values=timeseries)
    return rain_data


simulation_start_date.strftime("%Y-%m-%d") + 'T' + simulation_start_time

api_config = os.path.join(SCRIPT_DIR, '.env')
client = ThreediApiClient(env_file=api_config)
models = ThreedimodelsApi(client)
models_list = models.threedimodels_list(limit=100000000)
# for model in models_list.results:
#     print(model)

# select latest revision in repository
revision_number = 0
for model in models_list.results:
    if model.repository_slug == repository_slug:
        if int(model.revision_number) > revision_number:
            revision_number = int(model.revision_number)
            selected_model = model

# select Nelen & Schuurmans organisation id
organisations = OrganisationsApi(client)
organisation_id = organisations.organisations_list(name=organisation_name).results[0].unique_id

# create simulation
sim_api = SimulationsApi(client)
sim = Simulation(
    name='sim_name',
    threedimodel=selected_model.id,
    organisation=organisation_id,
    start_datetime=simulation_start_date.strftime("%Y-%m-%d") + 'T' + simulation_start_time,
    duration=simulation_duration_s,
)
created_sim = sim_api.simulations_create(sim)

# add rain events
sim_api = SimulationsApi(client)
rain_data = parse_rain_timeseries(rain_timeseries)
sim_api.simulations_events_rain_timeseries_create(
    created_sim.id, rain_data
)

# start simulation
sim_start = sim_api.simulations_actions_create(simulation_pk=created_sim.id, data={"name": "start"})
status = sim_api.simulations_status_list(created_sim.id, async_req=False)
print(status.name)
previous_status_name = status.name
while status.name != "finished":
    if status.name != previous_status_name:
        print(status.name)
        previous_status_name = status.name
    status = sim_api.simulations_status_list(created_sim.id, async_req=False)
    try:
        progress = sim_api.simulations_progress_list(created_sim.id, async_req=False)
        print("\r" + progress.percentage, end="")
    except openapi_client.exceptions.ApiException:
        pass
    time.sleep(.5)

# download results
dl.set_headers(lizard_username, lizard_password)  # TODO read credentials from the .env file
scenarios = dl.find_scenarios_by_model_slug(selected_model.slug, limit=10)
print(scenarios)
for scen in scenarios:
    fn = re.sub("[^0-9a-zA-Z]+", "-", scen['name']) + 'max_water_depth.tif'
    print('Waiting for Lizard to generate max water depth tif...')
    dl.download_maximum_waterdepth_raster(scen['uuid'],
                                          target_srs=srs,
                                          resolution=raster_resolution,
                                          pathname=os.path.join(out_dir, fn)
                                          )
dl.clear_inbox()

print('Finished!')
