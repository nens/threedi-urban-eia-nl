import os
import sqlite3
import json

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

# Create a table that contains nr_of_inhabitants per connection_node and iterate over it
for row in c.execute(
    "WITH inhibs_per_node AS (SELECT impsurf.id, impsurf.nr_of_inhabitants, impmap.connection_node_id FROM v2_impervious_surface impsurf, v2_impervious_surface_map impmap WHERE impsurf.nr_of_inhabitants IS NOT NULL AND impsurf.nr_of_inhabitants != 0 AND impsurf.id = impmap.impervious_surface_id) SELECT ipn.connection_node_id, SUM(ipn.nr_of_inhabitants) FROM inhibs_per_node ipn GROUP BY connection_node_id"
):
    data["dwfNode"].append(
        {
            "offset": 0,
            "values": [[0, 10], [20, 30]],
            "units": "m3/s",
            "connection_node": row[0],
        }
    )
    print(row)

# Close connection with spatialite
conn.close()

# DWF per person = 120 l/inhabitant / 1000 = 0.12 m3/inhabitant
dwfPerPerson = 0.12

dwfFactors = {
    "0-1": 0.015,
    "1-2": 0.015,
    "2-3": 0.015,
    "3-4": 0.015,
    "4-5": 0.015,
    "5-6": 0.03,
    "6-7": 0.04,
    "7-8": 0.05,
    "8-9": 0.06,
    "9-10": 0.065,
    "10-11": 0.075,
    "11-12": 0.085,
    "12-13": 0.075,
    "13-14": 0.065,
    "14-15": 0.06,
    "15-16": 0.05,
    "16-17": 0.05,
    "17-18": 0.05,
    "18-19": 0.04,
    "19-20": 0.035,
    "20-21": 0.03,
    "21-22": 0.025,
    "22-23": 0.02,
    "23-24": 0.02,
}

dwfFactors.update((x, y * dwfPerPerson) for x, y in dwfFactors.items())

print(dwfFactors)
