# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import logging
import argparse
import os 
import sys

logger = logging.getLogger(__name__)


class RksParser(object):
    """
    Parse rks files.
    """
    def __init__(self, rks_file_path, parse_immediately=True):
        """
        Args:
            rks_file_path: path to the rks rain series file
            parse_immediately: parse immediately after init
        """
        self.rks_file_path = rks_file_path

        self.event_timeseries = dict()  # actual data series
        self.event_nr_timesteps = dict()  # checker dict
        self.event_nr_dates = dict()  # dates for each event_nr
        self.timestep_duration = None
        self.data_integrity_errors = 0
        self.nr_of_events = 0
        self.has_parsed = 0

        if parse_immediately:
            self.parse_rks(self.rks_file_path)

    def parse_rks(self, rks_file_path):
        """
        The parser will recognize three types of lines:
            1) A line starting with '``* Aantal buien....``', followed by a
               line containing two integers.
            2) A line starting with '``*Event ...``', which is followed by
               three skippable lines and a line which contains date and
               duration information.
            3) Floats, but only when an event was found previously.
        """
        rks_file = open(rks_file_path)
        nr_of_events = 0
        event_nr = None
        data_integrity_errors = 0
        timestep_duration = None
        assumed_nr_of_events = None
        for line in rks_file:
            if line.startswith("* Aantal buien en tijdstapgrootte"):
                l = rks_file.__next__().split()
                assumed_nr_of_events, timestep_duration = list(map(int, l))
                timestep_duration /= 60.  # from s to min
                if not timestep_duration.is_integer():
                    raise Exception("Timestep duration cannot be converted "
                                    "to whole minutes: %s" %
                                    timestep_duration)
                else:
                    timestep_duration = int(timestep_duration)
            elif line.startswith('*Event'):
                line_list = line.split()
                event_nr = int(line_list[1])
                nr_of_events += 1
                self.event_timeseries[event_nr] = []

                # just skip 3 lines
                for i in range(3):
                    rks_file.__next__()

                # this line contains useful info
                info_line = rks_file.__next__()
                infos = info_line.split()
                (date_yr, date_mo, date_day, date_hr, date_min, date_sec,
                 days, hrs, mins, secs
                 ) = infos
                duration_min = (int(days)*24*60 + int(hrs)*60 + int(mins) +
                                int(secs) / 60.)
                nr_of_timesteps = duration_min / timestep_duration
                self.event_nr_timesteps[event_nr] = nr_of_timesteps
                self.event_nr_dates[event_nr] = "{}{}{}{}{}{}".format(
                    date_yr.zfill(4), date_mo.zfill(2), date_day.zfill(2),
                    date_hr.zfill(2), date_min.zfill(2), date_sec.zfill(2))

                logger.info("Event nr: %s, nr of timesteps (calculated) %s",
                            event_nr, nr_of_timesteps)
                if not nr_of_timesteps.is_integer():
                    logger.warning(
                        "WARNING: incorrect data. Number of timesteps not a "
                        "whole number for event {}".format(event_nr))
                    data_integrity_errors += 1
            elif event_nr:
                try:
                    p = float(line)
                except ValueError:
                    p = -9999
                    data_integrity_errors += 1
                    logger.warning("Error parsing a float for event {}"
                                   .format(event_nr))
                self.event_timeseries[event_nr].append(p)
        rks_file.close()

        # check if nr of parsed events equals the one in the file header
        if assumed_nr_of_events != nr_of_events:
            logger.warning(
                "WARNING: specified number of events ({}) and actual parsed"
                " number of events ({}) are not equal"
                .format(assumed_nr_of_events, nr_of_events))
            data_integrity_errors += 1

        # check if the nr of timeseries items parsed equals the expected
        # precomputed nr of timeseries items
        for ev_nr, ts in self.event_timeseries.items():
            computed_len = self.event_nr_timesteps[ev_nr]
            actual_len = len(ts)
            if actual_len != computed_len:
                logger.warning(
                    "WARNING: computed length ({}) and parsed length ({}) "
                    "of the timeseries of event {} are not equal"
                    .format(computed_len, actual_len, ev_nr))
                data_integrity_errors += 1

        self.timestep_duration = timestep_duration
        self.data_integrity_errors = data_integrity_errors
        self.nr_of_events = nr_of_events
        self.has_parsed += 1
        


def get_parser():
    """ Return argument parser. """
    parser = argparse.ArgumentParser()
    #POSITIONAL ARGUMENTS
    parser.add_argument('input_rks', metavar='Input RKS', help='Input RKS bestand')
    parser.add_argument('output_dir', metavar='Output directory', help='Output directory')
    
    #OPTIONAL ARGUMENTS
    parser.add_argument('--output-file-prefix', metavar='output_prefix', default=None, help='Prefix for the output filenames. Default is the original RKS filename.')
    parser.add_argument('--no-date', default=False, help='Dont include a date in the output', action='store_true')
    parser.add_argument('--no-padding', default=False, help="Dont pad output filenames with zeros.", action = 'store_true')
    
    return(parser)

def main():
    """ Call command with args from parser. """        
    kwargs = get_parser().parse_args()
    
    rks_file_path = kwargs.input_rks
    output_dir = kwargs.output_dir

    output_file_prefix = kwargs.output_file_prefix
    no_padding = kwargs.no_date
    no_date = kwargs.no_padding

    rks = RksParser(rks_file_path)
    event_timeseries = rks.event_timeseries
    event_nr_dates = rks.event_nr_dates
    timestep_duration = rks.timestep_duration
    data_integrity_errors = rks.data_integrity_errors
    nr_of_events = rks.nr_of_events

    if output_file_prefix is None:
        # NOTE: empty string is a-okay!
        rks_filename = os.path.splitext(os.path.basename(rks_file_path))[0]
        output_file_prefix = rks_filename

    if not no_padding:
        max_key = max(event_timeseries.keys())
        padding = len(str(max_key))
        logger.debug("Padding: %s", padding)

    # Construct filenames and write all the data to the output directory
    for ev_nr, ts in event_timeseries.items():
        filename = output_file_prefix + str(ev_nr).zfill(padding)
        if not no_date:
            filename = "{} {}".format(filename, event_nr_dates[ev_nr])
        output_filepath = os.path.join(output_dir, filename)
        with open(output_filepath, 'w') as f:
            for i, a in enumerate(ts):
                f.write("{},{}\n".format(i*timestep_duration, a))

    logger.info("Number of events: %s" % nr_of_events)
    if data_integrity_errors > 0:
        logger.warning("WARNING: process finished with {} possible errors"
                       .format(data_integrity_errors))
        sys.exit(1)
    else:
        logger.info("Finished without errors.")
        sys.exit(0)

if __name__ == '__main__':
    exit(main())
