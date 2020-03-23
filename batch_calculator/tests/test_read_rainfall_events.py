# -*- coding: utf-8 -*-
"""Tests for script.py"""
from batch_calculator.read_rainfall_events import BuiReader


def test_BuiReader():
    filepath = "C:/Users/Wout.Lexmond/notebooks/reeksberekeningen/reeks_10jr_1955_test/reeks_10jr_1955002 19550551124500"
    bui = BuiReader(filepath)
    assert (
        bui.filepath
        == "C:/Users/Wout.Lexmond/notebooks/reeksberekeningen/reeks_10jr_1955_test/reeks_10jr_1955002 19550551124500"
    )
