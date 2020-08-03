# -*- coding: utf-8 -*-
"""
Created on Tue Jul 14 11:23:54 2020

@author: Emile.deBadts
"""

import os
from batch_calculator.batch_calculation_statistics import batch_calculation_statistics


def test_batch_calculation_statistics():

    netcdf_dir = os.path.join(os.path.dirname(__file__), "aggregation_netcdfs")
    gridadmin = os.path.join(os.path.dirname(__file__), "gridadmin/gridadmin.h5")
    nr_years = 10

    statistics = batch_calculation_statistics(netcdf_dir, gridadmin, nr_years)

    assert statistics.iloc[1]["frequency"] == 0.6
    assert statistics.iloc[1]["average_volume"] == 333.8283264406019
    assert statistics.iloc[1]["t1"] == 0.0
    assert statistics.iloc[1]["t2"] == 101.21963132324407
    assert statistics.iloc[1]["t5"] == 821.1677606537347
    assert statistics.iloc[1]["t10"] == 876.728806098812

    assert statistics.iloc[0]["frequency"] == 0.6
    assert statistics.iloc[0]["average_volume"] == 180.17663379812973
    assert statistics.iloc[0]["t1"] == 0.0
    assert statistics.iloc[0]["t2"] == 77.0634225324484
    assert statistics.iloc[0]["t5"] == 427.9091279118319
    assert statistics.iloc[0]["t10"] == 451.625334322427
