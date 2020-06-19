import ast
import os

from datetime import datetime


class RainEventReader:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(self.filepath)

        # Default start_date
        self.start_date = "2020-01-01"

        # Try to read and set start_date from self.filename
        try:
            self.start_date = datetime.strftime(
                datetime.strptime(self.filename.split()[-1], "%Y%m%d%H%M%S"),
                "%Y-%m-%d",
            )
            print("start_date = " + str(self.start_date))
        except ValueError as e:
            print("Error: ", e)
            print("Using default date => start_date = " + str(self.start_date))

        # Default start_time
        self.start_time = "00:00:00"

        # Try to read start_time from filename, otherwise set default start_time
        try:
            self.start_time = datetime.strftime(
                datetime.strptime(self.filename.split()[-1], "%Y%m%d%H%M%S"),
                "%H:%M:%S",
            )
            print("start_time = " + str(self.start_time))
        except ValueError as e:
            print("Error: ", e)
            print("Using default time => start_time = " + str(self.start_time))

        # Combine self.start_date and self.start_time
        self.start_datetime = self.start_date + "T" + self.start_time

        # Open the rain-file
        with open(filepath, "r") as f:
            self.rain_timeseries = f.read()

        self.rain_data = self.parse_rain_timeseries()

        # Set the duration of the simulation to be equal to the last timestamp value and change the value from minutes to seconds
        self.duration = int(self.rain_data["values"][-1][0] * 60)

        print(self.rain_data)

    def parse_rain_timeseries(self):
        # This function parses 3Di-format rain files into the format required by the 3Di API

        rain_data = {"offset": 0, "interpolate": False, "values": [[0]], "units": "m/s"}
        timeseries = [
            list(ast.literal_eval(item))
            for item in self.rain_timeseries.split("\n")
            if item
        ]

        # Raise error if the first timestep in timeseries is not 0
        if timeseries[0][0] != 0:
            raise ValueError("First timestamp should be 0")

        # Raise error if the last rain intensity value in timeseries is larger than 0
        if timeseries[-1][1] != 0:
            raise ValueError("Last rain intensity value should be 0")

        # Calculate the timesteps from the list of timestamps in timeseries
        timesteps = [
            timeseries[i[0] + 1][0] - timeseries[i[0]][0]
            for i in enumerate(timeseries[0:-1])
        ]

        # Convert from [mm/timestep] to [m/s]
        timeseries_conv = [
            [element[0], element[1] / (timesteps[i] * 1000)] # removed 60 behind timesteps[i], since it seems like it is [m/min]
            for i, element in enumerate(timeseries[0:-1])
        ]

        # Append the last element of timeseries to timeseries_conv
        timeseries_conv.append(timeseries[-1])

        rain_data.update(values=timeseries_conv)
        return rain_data

    # def get_timeseries(self):

    #     return timeseries
