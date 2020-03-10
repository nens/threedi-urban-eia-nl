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
        # with open(filepath, "r") as f:
        #     for line in f:
        #         float_list = [float(i) for i in line.split('\n')]
        #         timeseries2 = [item.split('\n') for item in line]
        #         print(int_list)

        # with open(filepath, 'r') as f:
        #     lines = (line.strip() for line in f if line)
        #     x = [line for line in lines]
        #     print(x)

        # with open(filepath, "r") as f:
        #     self.rain_timeseries = [line.strip() for line in f if line]

        with open(filepath, "r") as f:
            self.rain_timeseries = f.read()

        rain_data = self.parse_rain_timeseries()
        self.timestep = rain_data["values"][1][0] - rain_data["values"][0][0]
        self.duration = rain_data["values"][-1][0] + self.timestep

        print(self.timestep, self.duration)

    #         # def find_duration(self) #waarom hier een functie definition?
    def parse_rain_timeseries(self):
        rain_data = {"offset": 0, "interpolate": False, "values": [[0]], "units": "m/s"}
        timeseries = [
            list(ast.literal_eval(item))
            for item in self.rain_timeseries.split("\n")
            if item
        ]

        rain_data.update(values=timeseries)
        # print(rain_data)
        return rain_data
