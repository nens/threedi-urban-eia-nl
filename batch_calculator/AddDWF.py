import os
import sqlite3
import json

from datetime import datetime

# Constants
# DWF per person = 120 l/inhabitant / 1000 = 0.12 m3/inhabitant
dwfPerPerson = 0.12

# Functie maken met aantal inwoners + starttijd + duration
baseDir = "C:/Users/Wout.Lexmond/notebooks/reeksberekeningen"
sqliteName = "loon.sqlite"
sqlitePath = os.path.join(baseDir, sqliteName)

conn = sqlite3.connect(sqlitePath)
c = conn.cursor()

# Create empty json structure
data = {}
data["dwfNode"] = []
timesteps = []  # Duration voor nodig uit read_rainfall_events?
dwfPerSec = (
    []
)  # dwfPerPerson * dwfFactor / 3600. Needs to be generated over the whole duration
dwfPerTimestep = [[timesteps[i], dwfPerSec[i]] for i in enumerate(timesteps[0:-1])]
dwfPerNode = []

# Create a table that contains nr_of_inhabitants per connection_node and iterate over it
for row in c.execute(
    "WITH inhibs_per_node AS (SELECT impsurf.id, impsurf.nr_of_inhabitants, impmap.connection_node_id FROM v2_impervious_surface impsurf, v2_impervious_surface_map impmap WHERE impsurf.nr_of_inhabitants IS NOT NULL AND impsurf.nr_of_inhabitants != 0 AND impsurf.id = impmap.impervious_surface_id) SELECT ipn.connection_node_id, SUM(ipn.nr_of_inhabitants) FROM inhibs_per_node ipn GROUP BY connection_node_id"
):
    dwfPerNode.append([row[0], row[1] * dwfPerPerson])

# print(dwfPerNode)

# Close connection with spatialite
conn.close()

# Create a list that holds all the dry weather flow percentages (factors). Source: Module C2100 Leidraad Riolering
dwfFactors = [
    [0, 0.015],
    [1, 0.015],
    [2, 0.015],
    [3, 0.015],
    [4, 0.015],
    [5, 0.03],
    [6, 0.04],
    [7, 0.05],
    [8, 0.06],
    [9, 0.065],
    [10, 0.075],
    [11, 0.085],
    [12, 0.075],
    [13, 0.065],
    [14, 0.06],
    [15, 0.05],
    [16, 0.05],
    [17, 0.05],
    [18, 0.04],
    [19, 0.035],
    [20, 0.03],
    [21, 0.025],
    [22, 0.02],
    [23, 0.02],
]

# Functie maken met aantal inwoners + starttijd + duration als input
def generate_upload_json_for_rain_event(
    dwf_on_each_node, rain_event_start_time, rain_event_duration
):
    """Generates a JSON-file that contains information about the dry weather flow on each connection node during the entire simulation."""

    # starting_hour not the right format yet
    # starting_hour = datetime.strftime(
    #     datetime.strptime(rain_event_start_time, "%H:%M:%S"), "%H"
    # )

    # Determine the starting hour
    starting_hour = datetime.strptime(rain_event_start_time, "%H:%M:%S").hour

    # Determine amount of seconds in first hour
    secs_in_first_hour = get_sec(
        datetime.strftime(datetime.strptime(rain_event_start_time, "%H:%M:%S"), "%M:%S")
    )
    if secs_in_first_hour == 0:
        secs_in_first_hour = 3600

    remaining_seconds = rain_event_duration - secs_in_first_hour
    print(remaining_seconds)
    remaining_hours = remaining_seconds // 3600
    print(remaining_hours)
    secs_in_last_hour = remaining_seconds % 3600
    print(secs_in_last_hour)

    dwfFactorPerTimestep = [
        [0, dwfFactors[starting_hour % 24][1]],
        [secs_in_first_hour, dwfFactors[(starting_hour + 1) % 24][1]],
    ]  # secs_in_first_hour moet 3600 zijn wanneer deze nul is

    number_of_whole_hours = list(range(remaining_hours))  # Check dit nog eens
    print(number_of_whole_hours)
    for h in number_of_whole_hours:
        # timesteps.append(timesteps[i] + 3600)
        new_timestep = dwfFactorPerTimestep[-1][0] + 3600
        newFactorHour = starting_hour + h + 2
        new_factor = dwfFactors[newFactorHour % 24][1]
        # dwfFactors[(starting_hour + i) % 24]
        dwfFactorPerTimestep.append([new_timestep, new_factor])

    # Append last timestep if there are seconds in the last hour
    if secs_in_last_hour > 0:
        dwfFactorPerTimestep.append(
            [new_timestep + secs_in_last_hour, dwfFactors[(newFactorHour + 1) % 24][1]]
        )
    # print(new_timestep)
    # Generate JSON for each connection node
    for i in enumerate(dwf_on_each_node):
        # dwfPerTimeStep = dwfFactorPerTimestep
        # print(dwf_on_each_node[i[0]][1])
        dwfPerTimeStep = [
            # Maybe with NUMPY
            [row[0], row[1] * dwf_on_each_node[i[0]][1]]
            for row in dwfFactorPerTimestep
        ]
        # [print(row) for j in row]
        # [row[0], row[1] * dwf_on_each_node[i][1]]
        # print(dwfPerTimeStep)
        # [j[0], j[1] * dwf_on_each_node[i][1]]
        data["dwfNode"].append(
            {
                "offset": 0,  # Wat doet offset bij laterals?
                "values": dwfPerTimeStep,  # multiply second value with nr_of_inhabitants (row[1])
                "units": "m3/s",
                "connection_node": dwf_on_each_node[i[0]][0],  # Might be i-1 or i+1
            }
        )

    return data["dwfNode"]


def get_sec(time_str):
    """Get Seconds from time."""
    m, s = time_str.split(":")
    return int(m) * 60 + int(s)


generate_upload_json_for_rain_event(dwfPerNode, "00:10:00", 14400)

print(data["dwfNode"])
