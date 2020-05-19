# -*- coding: utf-8 -*-
"""Tests for script.py"""
from batch_calculator.read_rainfall_events import RainEventReader


def test_RainEventReader():
    filepath = "C:/Users/Wout.Lexmond/notebooks/reeksberekeningen/reeks_10jr_1955_test/reeks_10jr_1955002 19550517124500"
    rain_event = RainEventReader(filepath)
    assert (
        rain_event.filepath
        == "C:/Users/Wout.Lexmond/notebooks/reeksberekeningen/reeks_10jr_1955_test/reeks_10jr_1955002 19550517124500"
    )
