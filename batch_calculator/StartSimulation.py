import logging
import time
import requests

from threedi_api_client.openapi import Simulation
from batch_calculator.AddDWF import generate_upload_json_for_rain_event

logger = logging.getLogger(__name__)

class SimulationStarter:
    def __init__(
        self,
        client,
        model_id,
        model_name,
        organisation_id,
        duration,
        rain_event_values,
        rain_event_start_time,
        dwf_per_node_24h,
        ini_2d_water_level_constant=None,
        ini_2d_water_level_raster_url=None,
        saved_state_url=None,
        simulation_template_id=None,
        start_datetime="2020-01-01T00:00:00",
        create_saved_state_end_simulation=False
    ):
        self._client = client
        self.model_id = model_id
        self.organisation_id = organisation_id
        self.saved_state_url = saved_state_url
        self.simulation_template_id = simulation_template_id
        self.start_datetime = start_datetime
        self.rain_event_start_time = rain_event_start_time
        self.rain_event_values = rain_event_values
        self.sim_name = model_name + "_" + self.start_datetime
        self.duration = duration
        self.ini_2d_water_level_constant = ini_2d_water_level_constant
        self.ini_2d_water_level_raster_url = ini_2d_water_level_raster_url
        self.dwf_per_node_24h = dwf_per_node_24h
        self.create_saved_state_end_simulation = create_saved_state_end_simulation
        self.simulation_succes = False

        
    def create_simulation(self):

        my_sim = Simulation(
            name=self.sim_name,
            threedimodel=self.model_id,
            organisation=self.organisation_id,
            start_datetime=self.start_datetime,
            duration=self.duration,
        )
        
        sim = self._client.simulations_create(my_sim)
        self.created_sim_id = sim.id
        self.sim_id_value = str(self.created_sim_id)
        print("   Current simulation ID: " + self.sim_id_value)
                
    def create_simulation_from_template(self):

        data = {"template": self.simulation_template_id,
                  "name": self.sim_name,
                  "organisation": self.organisation_id,
                  "start_datetime": self.start_datetime,
                  "duration": self.duration,
                  "clone_events": True, 
                  "clone_initials": True,
                  "clone_settings": True}

        sim = self._client.simulations_from_template(data)
        self.created_sim_id = sim.id
        self.sim_id_value = str(self.created_sim_id)
        print("   Current simulation ID: " + self.sim_id_value)
        
    def create_lateral_events_file(self):
    
        # Add dry weather flow (dwf) laterals
        dwf_json = generate_upload_json_for_rain_event(
            self.dwf_per_node_24h, self.rain_event_start_time, self.duration
        )

        # Create lateral upload instance
        dwf_upload = self._client.simulations_events_lateral_file_create(
            self.created_sim_id,
            {"filename": "dwf_sim_" + self.sim_id_value, "offset": 0},
        )

        # Upload dwf_json to lateral instance
        requests.put(dwf_upload.put_url, data=dwf_json)

        # Check if dwf file is uploaded
        print("   Waiting for DWF file to be uploaded and validated...")
        file_lateral = self._client.simulations_events_lateral_file_list(
            self.created_sim_id
        ).results[0]
        while file_lateral.state == "processing":
            time.sleep(5)
            file_lateral = self._client.simulations_events_lateral_file_read(
                id=file_lateral.id, simulation_pk=self.created_sim_id
            )
        if file_lateral.state != "valid":
            raise ValueError(
                f"Something went wrong during validation of file-lateral {file_lateral.id}"
            )
        print("   Using DWF lateral file:", file_lateral.url)

    def add_rain_timeseries_to_simulation(self):
        # Create a rain timeseries
        rain_upload = self._client.simulations_events_rain_timeseries_create(
            self.created_sim_id, self.rain_event_values
        )
        print("   Using rain timeseries:", rain_upload.url)

        # Check if a rain timeseries has been uploaded to the simulation (don't know yet how to check for the specific timeseries we just added)
        while self._client.simulations_events_rain_timeseries_list(self.created_sim_id).results == []:
            time.sleep(5)
    
    def add_initial_saved_state_to_simulation(self):
        # Add initial saved state
        self._client.simulations_initial_saved_state_create(
            self.created_sim_id, {"saved_state": self.saved_state_url},
        )
        print("   Using savedstate url: ", self.saved_state_url)
                
    def add_2d_waterlevel_raster(self):
        # saved state conflicts with 2d constant water level:
        self._client.simulations_initial2d_water_level_raster_create(
            self.created_sim_id,
            {
                "aggregation_method": "mean",
                "initial_waterlevel": self.ini_2d_water_level_raster_url,
            },
        )
        print(
            "   Using 2d waterlevel raster:", self.ini_2d_water_level_raster_url,
        )
        
        
    def add_global_2d_water_level(self):
        # Add constant global 2D waterlevel if no 2D waterlevel raster has been provided
        self._client.simulations_initial2d_water_level_constant_create(
            self.created_sim_id, {"value": self.ini_2d_water_level_constant},
        )
        print(
            "   Using constant 2d waterlevel: ",
            self.ini_2d_water_level_constant,
            " mNAP",
        )
        
    def simulations_create_saved_state_end_simulation(self):
        print('   Creating saved state at end of simulation...')
        
        self._client.simulations_create_saved_states_timed_create(
            self.created_sim_id,
            {
                "name": "saved_state_sim" + str(self.created_sim_id),
                "time": self.duration,
            },
        )
       
    def initialize_simulation(self):
        
        # Create a simulation with laterals/events/initials
        
        if self.simulation_template_id is not None:
            print('Creating simulation from template...')
            sim = self.create_simulation_from_template()
            
            # Remove events from simulation
            rain_events = self._client.simulations_events_rain_timeseries_list(self.created_sim_id).results
            for event in rain_events:                
                self._client.simulations_events_rain_timeseries_delete(id=event.id, simulation_pk=self.created_sim_id)
                            
            self.add_rain_timeseries_to_simulation()
            if self.saved_state_url is not None:
                self.add_initial_saved_state_to_simulation()
            elif self.ini_2d_water_level_raster_url is not None:
                self.add_2d_waterlevel_raster()
            elif self.ini_2d_water_level_constant is not None:
                self.add_global_2d_water_level()
            
            if self.create_saved_state_end_simulation:
                self.simulations_create_saved_state_end_simulation()                  
            
            
        else:
            print('Creating simulation from scratch...')
            sim = self.create_simulation()
            
            if self.dwf_per_node_24h is not None:
                self.create_lateral_events_file()
                
            self.add_rain_timeseries_to_simulation()
            
            # Add either a saved state, a 2d initial water levels, or a 2d constant water level
            if self.saved_state_url is not None:
                self.add_initial_saved_state_to_simulation()
            elif self.ini_2d_water_level_raster_url is not None:
                self.add_2d_waterlevel_raster()
            elif self.ini_2d_water_level_constant is not None:
                self.add_global_2d_water_level()
            
            if self.create_saved_state_end_simulation:
                self.simulations_create_saved_state_end_simulation()
            
    def run_simulation(self):
        
        # Run the created simulation and wait for completion
        # Check if created simulation has logical settings

        # Check if 2D waterlevel is provided
        waterlvl_2d_const = self._client.simulations_initial2d_water_level_constant_list(
            self.created_sim_id
        )
        waterlvl_2d_raster = self._client.simulations_initial2d_water_level_raster_list(
            self.created_sim_id
        )

        if waterlvl_2d_const.count == 0 and waterlvl_2d_raster.count == 0:
            logger.warning("No 2D waterlevel has been provided")

        # Start the simulation with id = created_sim_id
        self._client.simulations_actions_create(
            simulation_pk=self.created_sim_id, data={"name": "queue"}
        )

        # Print the status of the simulation while it is not yet initialized
        status = self._client.simulations_status_list(self.created_sim_id, async_req=False)
        print(status.name, end="\r", flush=True)
        while (
            status.name != "initialized"
        ):  # old code: status.name == "queued" or status.name == "starting":
            print(status.name, end="\r", flush=True)
            status = self._client.simulations_status_list(
                self.created_sim_id, async_req=False
            )
            time.sleep(5.0)
        print(status.name)

        self._client.simulations_progress_list(self.created_sim_id, async_req=False)

        # Required, otherwise DownloadResults tries downloading while simulation is still running
        # Sometimes gets stuck
        progress = self._client.simulations_progress_list(
            self.created_sim_id, async_req=False
        )
        while progress.percentage < 100:
            progress = self._client.simulations_progress_list(
                self.created_sim_id, async_req=False
            )
            print(progress.percentage, "%", end="\r", flush=True)
            time.sleep(1.0)

        # Check saved state upload
        if self.create_saved_state_end_simulation:
            saved_states = self._client.simulations_create_saved_states_timed_list(self.created_sim_id)
            saved_state_end = saved_states.results[0]
            self.saved_state_end_duration_url = saved_state_end.url
            
        self.simulation_succes = True
