import logging
import sys
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


def _get_stdout_logger(name: str = "default_stdout_logger") -> logging.Logger:
    """
    Return a logger that logs to sys.stdout (like print()).
    Ensures we don't add duplicate handlers across repeated calls.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)           # choose your default level
    logger.propagate = False                # don't bubble to root unless you want that

    # Add a stdout handler only once
    if not any(isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout
               for h in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")  # mimic plain print()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def structure_control_logic(
        api_client: V3Api,
        simulation: Simulation,
        simulation_current_time: int,
        structures: Dict[str, Structure],
        measure_locations: Dict[str, MeasureLocation],
        measure_frequency: float,
        logger: logging.Logger | None = None,
):
    logger = logger or _get_stdout_logger()
    if all([structure.is_open for structure in structures.values()]):  # als alle stuwputten open staan...
        logger.debug("Alle stuwputten zijn open")

        try:
            logger.debug(
                f"time step, voorlaatste waterstand Lokhorstweg: {measure_locations['Lokhorstweg'].water_levels[-2] if len(measure_locations['Lokhorstweg'].water_levels) > 1 else None }")
        except IndexError:
            pass
        logger.debug(f"time step, laatste waterstand Lokhorstweg: {measure_locations['Lokhorstweg'].water_levels[-1]}")
        logger.debug(f"Lokhorstweg is boven 7.10: {measure_locations['Lokhorstweg'].water_levels[-1][-1] > 7.10}")
        logger.debug(f"Lokhorstweg is aan het stijgen: {measure_locations['Lokhorstweg'].is_rising}")

        logger.debug(f"time step, voorlaatste waterstand R01: {measure_locations['RO1'].water_levels[-2]  if len(measure_locations['RO1'].water_levels) > 1 else None }")
        logger.debug(f"time step, laatste waterstand R01: {measure_locations['RO1'].water_levels[-1]}")
        logger.debug(f"RO1 is boven 0.0: {measure_locations['RO1'].water_levels[-1][-1] > 0.0}")
        logger.debug(f"RO1 is aan het stijgen: {measure_locations['RO1'].is_rising}")

        if measure_locations["Lokhorstweg"].water_levels[-1][-1] > 7.1 and \
                measure_locations["Lokhorstweg"].is_rising:
            # Case: stuwputten staan open en moeten dichtgezet worden; verandering, dus loggen
            logger.debug(f"Reden voor actie: waterstand Lokhorstweg is te hoog geworden.")
            log_level = logging.INFO
            action = "close"
        elif measure_locations["RO1"].water_levels[-1][-1] > 0.0 and \
                measure_locations["RO1"].is_rising:
            # Case: stuwputten staan open en moeten dichtgezet worden; verandering, dus loggen
            logger.debug(f"Reden voor actie: waterstand RO1 is te hoog geworden.")
            log_level = logging.INFO
            action = "close"
        else:
            # Case: stuwputten staan open en moeten open blijven; geen verandering, dus niet loggen
            logger.debug(f"Reden voor actie: stuwputten staan open en moeten open blijven.")
            log_level = logging.DEBUG
            action = "open"
    elif not any([structure.is_open for structure in structures.values()]):  # als alle stuwputten dicht staan...
        logger.debug("Alle stuwputten zijn dicht")

        logger.debug(f"RO1 is 4 cm gedaald: {measure_locations['RO1'].is_below_last_peak(threshold=0.04)}")
        logger.debug(f"time step, voorlaatste waterstand R01: {measure_locations['RO1'].water_levels[-2] if len(measure_locations['RO1'].water_levels) > 1 else None }")
        logger.debug(f"time step, laatste waterstand R01: {measure_locations['RO1'].water_levels[-1]}")
        logger.debug(f"RO1 is onder 0.46: {measure_locations['RO1'].water_levels[-1][-1] < 0.46}")
        logger.debug(f"RO1 is aan het dalen: {measure_locations['RO1'].is_falling}")

        logger.debug(f"time step, voorlaatste waterstand Lokhorstweg: {measure_locations['Lokhorstweg'].water_levels[-2] if len(measure_locations['Lokhorstweg'].water_levels) > 1 else None }")
        logger.debug(f"time step, laatste waterstand Lokhorstweg: {measure_locations['Lokhorstweg'].water_levels[-1]}")
        logger.debug(f"Lokhorstweg is onder 7.00: {measure_locations['Lokhorstweg'].water_levels[-1][-1] < 7.00}")

        logger.debug(f"RO1 is onder 0.0: {measure_locations['RO1'].water_levels[-1][-1] < 0.0}")

        if (
                measure_locations['RO1'].is_below_last_peak(threshold=0.04)
                and
                (measure_locations["RO1"].water_levels[-1][-1]) < 0.46
                and
                measure_locations["RO1"].is_falling
                and
                (measure_locations["Lokhorstweg"].water_levels[-1][-1]) < 7.00
                and
                measure_locations["Lokhorstweg"].is_falling
        ):
            # Case: stuwputten staan dicht en moeten open gezet worden; verandering, dus loggen
            logger.debug(f"Reden voor actie: RO1 is 4 cm gedaald en < 0.46, Lokhorstweg < 7.00.")
            log_level = logging.INFO
            action = "open"
        elif measure_locations["RO1"].water_levels[-1][-1] < 0.00:
            # Case: stuwputten staan dicht en moeten open gezet worden; verandering, dus loggen
            logger.debug(f"Reden voor actie: RO1 is onder 0")
            log_level = logging.INFO
            action = "open"
        else:
            # Case: stuwputten staan dicht en moeten dicht blijven; geen verandering, dus niet loggen
            logger.debug(f"Reden voor actie: stuwputten staan dicht en moeten dicht blijven.")
            log_level = logging.DEBUG
            action = "close"
    else:
        raise NotImplementedError(
            "Sommige stuwputten zijn open en sommige dicht, hier kan de regeling niet mee omgaan"
        )
    logger.log(level=log_level, msg=f"Time step: {simulation_current_time}. Action: {action} all three orifices...")
    if action == "close":
        for structure in structures.values():
            structure.close_valve(
                api_client=api_client,
                simulation=simulation,
                offset=simulation_current_time,
                duration=measure_frequency + 10.0 * 2,  # let this timed control be active for measure_frequency seconds
                                                        # plus two calculation time steps to avoid gaps between
                                                        # timed controls
            )
    elif action == "open":
        for structure in structures.values():
            structure.open_valve()
    else:
        raise RuntimeError("action should be 'open' or 'close'")
