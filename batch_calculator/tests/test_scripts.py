# -*- coding: utf-8 -*-
"""Tests for script.py"""
import mock

from batch_calculator import scripts


@mock.patch(
    "sys.argv",
    [
        "program",
        "C:/Users/Wout.Lexmond/notebooks/reeksberekeningen/reeks_10jr_1955_test",
        "61f5a464c35044c19bc7d4b42d7f58cb",
        "C:/Users/Wout.Lexmond/notebooks/reeksberekeningen/output",
    ],
)
def test_get_parser():
    parser = scripts.get_parser()
    # As a test, we just check one option. That's enough.
    options = parser.parse_args()
    assert options.verbose == False
