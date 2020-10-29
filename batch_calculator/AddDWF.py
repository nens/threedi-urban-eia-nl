import os
import sqlite3
import json

from datetime import datetime

# Functie maken met aantal inwoners + starttijd + duration
# baseDir = "C:/Users/Wout.Lexmond/notebooks/reeksberekeningen"
# sqliteName = "loon.sqlite"
# sqlitePath = os.path.join(baseDir, sqliteName)


def read_dwf_per_node(spatialite_path):
    """Obtains the 24h dry weather flow per connection node from the a 3Di model sqlite-file."""
    conn = sqlite3.connect(spatialite_path)
    c = conn.cursor()

    # DWF per person = 120 l/inhabitant / 1000 = 0.12 m3/inhabitant
    dwfPerPerson = 0.12

    # Create empty list that holds total 24h dry weather flow per node
    dwfPerNode24h = []

    cnt = 0
    # Create a table that contains nr_of_inhabitants per connection_node and iterate over it
    for row in c.execute(
        "WITH imp_surface_count AS ( SELECT impsurf.id, impsurf.nr_of_inhabitants / COUNT(impmap.impervious_surface_id) AS nr_of_inhabitants FROM v2_impervious_surface impsurf, v2_impervious_surface_map impmap WHERE impsurf.nr_of_inhabitants IS NOT NULL AND impsurf.nr_of_inhabitants != 0 AND impsurf.id = impmap.impervious_surface_id GROUP BY impsurf.id), inhibs_per_node AS ( SELECT impmap.impervious_surface_id, impsurfcount.nr_of_inhabitants, impmap.connection_node_id FROM imp_surface_count impsurfcount, v2_impervious_surface_map impmap WHERE impsurfcount.id = impmap.impervious_surface_id) SELECT ipn.connection_node_id, SUM(ipn.nr_of_inhabitants) FROM inhibs_per_node ipn GROUP BY ipn.connection_node_id"
    ):
        dwfPerNode24h.append([row[0], row[1] * dwfPerPerson / 3600])

        cnt += row[1]
    #  OLD QUERY:       "WITH inhibs_per_node AS (SELECT impmap.impervious_surface_id, impsurf.nr_of_inhabitants, impmap.connection_node_id FROM v2_impervious_surface impsurf, v2_impervious_surface_map impmap WHERE impsurf.nr_of_inhabitants IS NOT NULL AND impsurf.nr_of_inhabitants != 0 AND impsurf.id = impmap.impervious_surface_id), imp_surface_count AS (SELECT impervious_surface_id, COUNT(*) AS cnt FROM inhibs_per_node GROUP BY impervious_surface_id) SELECT ipn.connection_node_id, SUM(ipn.nr_of_inhabitants) / isc.cnt FROM inhibs_per_node ipn, imp_surface_count isc WHERE ipn.impervious_surface_id = isc.impervious_surface_id GROUP BY ipn.connection_node_id"

    # Print the number of inhabitants
    print("DWF of:", cnt, "inhabitants")

    # Close connection with spatialite
    conn.close()

    # print("DWF PER NODE (inhabitants * 0.12 m3/day):")
    # print(dwfPerNode24h)
    return dwfPerNode24h


# Create a list that holds all the dry weather flow percentages (factors). Source: Module C2100 Leidraad Riolering
dwfFactors = [
    [0, 0.03],
    [1, 0.015],
    [2, 0.01],
    [3, 0.01],
    [4, 0.005],
    [5, 0.005],
    [6, 0.025],
    [7, 0.080],
    [8, 0.075],
    [9, 0.06],
    [10, 0.055],
    [11, 0.05],
    [12, 0.045],
    [13, 0.04],
    [14, 0.04],
    [15, 0.035],
    [16, 0.035],
    [17, 0.04],
    [18, 0.055],
    [19, 0.08],
    [20, 0.07],
    [21, 0.055],
    [22, 0.045],
    [23, 0.04],
]

# Functie maken met aantal inwoners + starttijd + duration als input
def generate_upload_json_for_rain_event(
    dwf_on_each_node, rain_event_start_time, rain_event_duration
):
    """Generates a JSON-file that contains information about the dry weather flow on each connection node during the entire simulation."""

    # Determine the starting hour
    starting_hour = datetime.strptime(rain_event_start_time, "%H:%M:%S").hour

    # Determine amount of seconds in first hour
    secs_in_first_hour = get_sec(
        datetime.strftime(datetime.strptime(rain_event_start_time, "%H:%M:%S"), "%M:%S")
    )
    if secs_in_first_hour == 0:
        secs_in_first_hour = 3600

    # Calculate the seconds remaining
    remaining_seconds = rain_event_duration - secs_in_first_hour

    # Calculate the whole hours remaining
    remaining_hours = remaining_seconds // 3600

    # Calculate the seconds remaining in the last hour
    secs_in_last_hour = remaining_seconds % 3600

    # Create a list that will hold the dwf factor for each timestep of the 1D lateral and fill with the first two timesteps
    dwfFactorPerTimestep = [
        [0, dwfFactors[starting_hour % 24][1]],
        [secs_in_first_hour, dwfFactors[(starting_hour + 1) % 24][1]],
    ]

    number_of_whole_hours = list(range(1, remaining_hours + 1))
    # Loop over the remaining whole hours and append the new timesteps and their corresponding dwf factors
    for h in number_of_whole_hours:
        new_timestep = dwfFactorPerTimestep[-1][0] + 3600
        newFactorHour = starting_hour + h + 1
        new_factor = dwfFactors[newFactorHour % 24][1]
        dwfFactorPerTimestep.append([new_timestep, new_factor])

    # Append last timestep if there are seconds in the last hour
    if secs_in_last_hour > 0:
        dwfFactorPerTimestep.append(
            [new_timestep + secs_in_last_hour, dwfFactors[(newFactorHour + 1) % 24][1]]
        )

    # Initialize list that will hold JSON
    dwf_list = []

    # Generate JSON for each connection node
    for i in enumerate(dwf_on_each_node):

        # print(dwf_on_each_node[i[0]][1])
        dwfPerTimeStep = [
            [row[0], row[1] * dwf_on_each_node[i[0]][1]] for row in dwfFactorPerTimestep
        ]

        dwf_list.append(
            {
                "offset": 0,
                "interpolate": 0,
                "values": dwfPerTimeStep,
                "units": "m3/s",
                "connection_node": dwf_on_each_node[i[0]][0],
            }
        )

    dwf_json = json.dumps(dwf_list,indent=4)
    return dwf_json


def get_sec(time_str):
    """Get Seconds from time."""
    m, s = time_str.split(":")
    return int(m) * 60 + int(s)


# dwfPerNode24h = read_dwf_per_node(sqlitePath)
# data = generate_upload_json_for_rain_event(dwfPerNode24h, "00:10:00", 14400)

# with open(os.path.join(baseDir, "data.json"), "w") as f:
#     json.dump(data, f, indent=4)
