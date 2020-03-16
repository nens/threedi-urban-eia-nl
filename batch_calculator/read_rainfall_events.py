import ast

from datetime import datetime


class BuiReader:
    def __init__(self, filepath):
        self.filepath = filepath

        self.start_date = datetime.strftime(
            datetime.strptime(self.filepath.split()[1], "%Y%m%d%H%M%S"), "%Y-%m-%d",
        )

        self.start_time = datetime.strftime(
            datetime.strptime(self.filepath.split()[1], "%Y%m%d%H%M%S"), "%H:%M:%S",
        )

        self.start_datetime = self.start_date + "T" + self.start_time

        self.end_datetime = self.start_datetime

        with open(filepath, "r") as f:
            self.rain_timeseries = f.read()

        self.rain_data = self.parse_rain_timeseries()
        print(self.rain_data)
        self.timestep = self.rain_data["values"][1][0] - self.rain_data["values"][0][0]

        # Convert duration from mins to seconds
        self.duration = int( ( self.rain_data["values"][-1][0] + self.timestep ) * 60 )

    def parse_rain_timeseries(self):
        rain_data = {"offset": 0, "interpolate": False, "values": [[0]], "units": "m/s"}
        timeseries = [
            list(ast.literal_eval(item))
            for item in self.rain_timeseries.split("\n")
            if item
        ]
        
        # Convert from [mm/15min] to [m/s]
        timeseries = [ [element[0], element[1] / (900 * 1000)] for element in timeseries]
        # print(timeseries)

        rain_data.update(values=timeseries)
        return rain_data

    # def get_timeseries(self):

    #     return timeseries
