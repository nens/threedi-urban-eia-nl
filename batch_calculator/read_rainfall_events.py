import ast
import os

from datetime import datetime


class BuiReader:
    def __init__(self, filepath):
        self.filepath = filepath

        filename = os.path.basename(self.filepath)
        self.start_date = "2020-01-01"
        # if
        # TODO filepath naar filename
        # defaultwaarde
        # Try to read start_date from filename, otherwise set default start_date
        try:
            self.start_date = datetime.strftime(
                datetime.strptime(self.filepath.split()[-1], "%Y%m%d%H%M%S"),
                "%Y-%m-%d",
            )
            print("start_date = " + str(self.start_date))
        except ValueError as e:  # uitzoeken welke exception hier geraised moet worden
            print("Error: ", e)
            self.start_date = "2020-01-01"
            print("Using default date => start_date = " + str(self.start_date))

        # Try to read start_time from filename, otherwise set default start_time
        try:
            self.start_time = datetime.strftime(
                datetime.strptime(self.filepath.split()[-1], "%Y%m%d%H%M%S"),
                "%H:%M:%S",
            )
            print("start_time = " + str(self.start_time))
        except ValueError as e:  # uitzoeken welke exception hier geraised moet worden
            print("Error: ", e)
            self.start_time = "00:00:00"
            print("Using default time => start_time = " + str(self.start_time))

        # Combine self.start_date and self.start_time
        self.start_datetime = self.start_date + "T" + self.start_time

        # Open the rain-file
        with open(filepath, "r") as f:
            self.rain_timeseries = f.read()

        self.rain_data = self.parse_rain_timeseries()

        # self.last_timestep = (
        #     self.rain_data["values"][-1][0] - self.rain_data["values"][-2][0]
        # )

        # Set the duration of the simulation to be equal to the last timestamp value and change the value from minutes to seconds
        self.duration = int(self.rain_data["values"][-1][0] * 60)

    def parse_rain_timeseries(self):
        # This function parses 3Di-format rain files into the format required by the 3Di API

        rain_data = {"offset": 0, "interpolate": False, "values": [[0]], "units": "m/s"}
        timeseries = [
            list(ast.literal_eval(item))
            for item in self.rain_timeseries.split("\n")
            if item
        ]

        # Convert from [mm/15min] to [m/s] (TODO: change so that it works for all timesteps)
        timeseries = [
            [element[0], element[1] / (15 * 60 * 1000)] for element in timeseries
        ]

        # Raise error if the first timestep in timeseries is not 0
        if timeseries[0][0] != 0:
            raise ValueError("First timestamp should be 0")

        # Raise error if the last rain intensity value in timeseries is larger than 0
        if timeseries[-1][1] != 0:
            raise ValueError("Last rain intensity value should be 0")

        rain_data.update(values=timeseries)
        return rain_data

    # def get_timeseries(self):

    #     return timeseries
