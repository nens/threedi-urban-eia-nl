# -*- coding: utf-8 -*-
"""Tests for script.py"""
from batch_calculator.read_rainfall_events import BuiReader


def test_BuiReader():
    filepath = "hoi.txt"
    bui = BuiReader(filepath)
    assert bui.filepath == "hoi.txt"
