from typing import Dict

from threedi_api_client.openapi import Simulation
from threedi_api_client.openapi.api.v3_api import V3Api

from complex_structure_control import MeasureLocation, Structure

MEASURE_LOCATIONS = {
    "Lokhorstweg": MeasureLocation(
        code="H1393",
        name="Lokhorstweg",
        connection_node_id=22622,
    ),
    "RO1": MeasureLocation(
        code="602F513",
        name="RO1",
        connection_node_id=5220,
    ),
}

STRUCTURES = {
    "Stationsplein": Structure(
        type="orifice",
        id=10857,
        name="Stationsplein",
        code="C604-C681",
        discharge_coefficients=[0.8, 0.8]
    ),
    "Sophialaan": Structure(
        type="orifice",
        id=10850,
        name="Sophialaan",
        code="G1243A-",
        discharge_coefficients=[0.8, 0.8]
    ),
    "Hoenderweg": Structure(
        type="orifice",
        code="G1240-H1403",
        name="Hoenderweg",
        id=10860,
        discharge_coefficients=[0.8, 0.8]
    ),
}


def structure_control_logic(
        api_client: V3Api,
        simulation: Simulation,
        simulation_current_time: int,
        structures: Dict[str, Structure],
        measure_locations: Dict[str, MeasureLocation],
):
    if all([structure.is_open for structure in structures.values()]):  # als alle stuwputten open staan...
        if (
                (
                        (measure_locations["Lokhorstweg"].water_levels[-1]) > 7.1
                        and
                        measure_locations["Lokhorstweg"].is_rising
                )
                or
                (
                        (measure_locations["RO1"].water_levels[-1]) > 0.0
                        and
                        measure_locations["RO1"].is_rising
                )
        ):
            # alle stuwputten dicht zetten
            print("Alle stuwputten dichtzetten...")
            for structure in STRUCTURES.values():
                structure.set_valve(
                    api_client=api_client,
                    simulation=simulation,
                    action="close",
                    offset=simulation_current_time,
                    duration=simulation.duration,  # let this action be active until a new action is activated
                )
            print("Alle stuwputten dichtgezet.")
    elif not any([structure.is_open for structure in STRUCTURES.values()]):  # als alle stuwputten dicht staan...
        if (
                (
                        measure_locations['RO1'].is_below_last_peak(threshold=0.04)
                        and
                        (measure_locations["RO1"].water_levels[-1]) < 0.46
                        and
                        measure_locations["RO1"].is_falling
                        and
                        (measure_locations["Lokhorstweg"].water_levels[-1]) < 7.00
                        and
                        measure_locations["Lokhorstweg"].is_falling
                )
                or
                (
                        (measure_locations["RO1"].water_levels[-1]) < 0.00
                )
        ):
            # alle stuwputten open zetten
            print("Alle stuwputten openzetten...")
            for structure in structures.values():
                structure.set_valve(
                    api_client=api_client,
                    simulation=simulation,
                    action="open",
                    offset=simulation_current_time,
                    duration=simulation.duration,  # let this action be active until a new action is activated
                )
            print("Alle stuwputten open gezet.")
    else:
        raise NotImplementedError(
            "Sommige stuwputten zijn open en sommige dicht, hier kan de regeling niet mee omgaan"
        )



