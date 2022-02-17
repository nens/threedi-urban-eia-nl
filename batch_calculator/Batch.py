import os
import datetime

from batch_calculator.read_rainfall_events import RainEventReader
from batch_calculator.AddDWF import read_dwf_per_node
from batch_calculator.StartSimulation import StartSimulation
from batch_calculator.DownloadResults import DownloadResults

MAX_LENGTH_RAIN_EVENT = 300

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
            self._client.threedimodels_initial_waterlevels_list(
                self.model_id
            ).count
            == 1
        ):
            self.ini_2d_water_level_raster_url = (
                self._client.threedimodels_initial_waterlevels_list(
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
            rain_event_start_datetime = datetime.datetime.strptime(rain_event.start_datetime, "%Y-%m-%dT%H:%M:%S")
            
            rain_event_length = len(rain_event.rain_data['values'])
            saved_state = self.saved_state_url
            
            if rain_event_length > MAX_LENGTH_RAIN_EVENT:
                
                print('Length rain event is >300, dividing into smaller chunks...')
                
                # Loop over rain subsets of size 300 or smaller
                
                for rain_subset_values in rain_event.batch():
                    
                    rain_subset_values_shifted = [[time-rain_subset_values[0][0], value] for time,value in rain_subset_values]
                    rain_subset_data = {'offset':0, 
                                        'interpolate':False, 
                                        'values':rain_subset_values_shifted,
                                        'units':'m/s'}
                    
                    rain_subset_duration = rain_subset_values[-1][0] - rain_subset_values[0][0]
                    rain_subset_start_datetime = rain_event_start_datetime + datetime.timedelta(seconds=rain_subset_values[0][0])
                    rain_subset_start_datetime_str = rain_subset_start_datetime.isoformat() 
                    rain_subset_starttime = rain_subset_start_datetime.time().isoformat()
                    
                    print('Starting with rain subset {}...'.format(rain_subset_start_datetime_str))
                                        
                    sim = StartSimulation(
                        self._client,
                        self.model_id,
                        self.model_name,
                        self.org_id,
                        rain_subset_duration,
                        rain_subset_data,
                        rain_subset_starttime,                        
                        dwf_per_node_24h,
                        self.ini_2d_water_level_constant,
                        self.ini_2d_water_level_raster_url,
                        saved_state,
                        start_datetime=rain_subset_start_datetime_str,
                        create_saved_state_end_simulation=True
                    )
                    
                    saved_state = sim.saved_state_end_duration_url
                
                results = DownloadResults(
                    self._client, sim.created_sim_id, sim.model_id, self.results_dir
                )                
                
            
            else:
                # Start simulation normally                     
                sim = StartSimulation(
                    self._client,
                    self.model_id,
                    self.model_name,
                    self.org_id,
                    rain_event.duration,
                    rain_event.rain_data,
                    rain_event.start_time,
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
