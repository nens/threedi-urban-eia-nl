# -*- coding: utf-8 -*-
"""
Created on Mon May 18 14:09:04 2020

@author: Emile.deBadts
"""

import argparse
import pandas
import os
from math import floor

from threedigrid.admin.gridresultadmin import GridH5AggregateResultAdmin

STATS = [1, 2, 5, 10]


def get_args():
    """Get command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process aggregate netCDF files to weir statistics."
    )
    parser.add_argument(
        "netcdf_dir", metavar="NETCDF_DIR", help="netcdf directory",
    )
    parser.add_argument(
        "gridadmin_file", metavar="GRIDADMIN_FILE", help="gridadmin",
    )
    parser.add_argument(
        "nr_years",
        metavar="JAREN",
        choices=["10", "25"],
        help="Batch calculation length (10 or 25 years)",
    )
    return parser.parse_args()


def repetition_time_volumes(weir_results, n, stats=[1, 2, 5, 10]):

    sorted_weir_results = sorted(list(weir_results), reverse=True)
    print(sorted_weir_results)
    if n == 10:
        T_volume_list = []
        for T in stats:
            if T == 5:
                volume = sorted_weir_results[1] - 0.48 * (
                    sorted_weir_results[1] - sorted_weir_results[2]
                )
                T_volume_list += [volume]
            elif T == 10:
                volume = sorted_weir_results[0] - 0.46 * (
                    sorted_weir_results[0] - sorted_weir_results[1]
                )
                T_volume_list += [volume]
            else:
                T_volume_list += [sorted_weir_results[int(n / T) - 1]]

    if n == 25:
        T_volume_list = []
        for T in stats:
            if (n / T).is_integer():
                T_volume_list += [sorted_weir_results[int(n / T) - 1]]
            else:
                volume = sorted_weir_results[floor(n / T) - 1] - 0.5 * (
                    sorted_weir_results[floor(n / T) - 1]
                    - sorted_weir_results[floor(n / T)]
                )
                T_volume_list += [volume]

    return T_volume_list


def batch_calculation_statistics(netcdf_dir, gridadmin, nr_years):

    nc_files = [file for file in os.listdir(netcdf_dir) if file.endswith(".nc")]
    ga = GridH5AggregateResultAdmin(gridadmin, os.path.join(netcdf_dir, nc_files[0]))
    weir_pks = ga.lines.filter(content_type="v2_weir").only("content_pk").data
    results = pandas.DataFrame(columns=["aggregate_netcdf", *weir_pks["content_pk"]])

    for i, aggregate_file in enumerate(nc_files):
        ga = GridH5AggregateResultAdmin(
            gridadmin, os.path.join(netcdf_dir, aggregate_file)
        )
        weir_data = (
            ga.lines.filter(content_type="v2_weir")
            .only("content_pk", "content_type", "q_cum")
            .timeseries(indexes=slice(None))
            .data
        )
        cumulative_discharge = [x for x in weir_data["q_cum"][-1]]
        results.loc[i] = [aggregate_file, *cumulative_discharge]

    # Find results for each weir
    output = pandas.DataFrame(
        columns=["weir_id", "frequency", "average_volume", "t1", "t2", "t5", "t10",]
    )

    for i, weir in enumerate(results.columns[1:]):

        frequency = float(sum(results[weir] > 0) / nr_years)
        average_volume = sum(results[weir]) / nr_years

        weir_tx_list = [
            *repetition_time_volumes(weir_results=results[weir], n=nr_years)
        ]

        output.loc[i] = [
            weir,
            frequency,
            average_volume,
            *weir_tx_list,
        ]

    return output


def main():

    args = get_args()

    #    netcdf_dir = 'Y:/E_deBadts/batch_calculator/aggregation_netcdfs'
    #    gridadmin = 'Y:/E_deBadts/batch_calculator/gridadmin/gridadmin.h5'
    #    nr_years = 10

    nc_dir = args.netcdf_dir
    gridadmin = args.gridadmin_file
    nr_years = int(args.nr_years)

    batch_calculation_stats_table = batch_calculation_statistics(
        netcdf_dir=nc_dir, gridadmin=gridadmin, nr_years=nr_years
    )

    batch_calculation_stats_table.to_csv(
        os.path.join(os.path.dirname(__file__), "batch_calculator_statistics.csv"),
        index=False,
    )


if __name__ == "__main__":
    main()
