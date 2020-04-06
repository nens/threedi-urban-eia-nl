# -*- coding: utf-8 -*-
"""Tests for script.py"""
import os
import mock

from batch_calculator import scripts
from batch_calculator.read_rainfall_events import BuiReader

# Arguments required by the parser
rain_files_dir = os.path.relpath("tests/reeks_10jr_1955_test")
org_id = "61f5a464c35044c19bc7d4b42d7f58cb"
results_dir = os.path.relpath("tests/output")


@mock.patch(
    "sys.argv",
    ["program", rain_files_dir, "61f5a464c35044c19bc7d4b42d7f58cb", results_dir,],
)
def test_get_parser():
    parser = scripts.get_parser()
    # As a test, we just check one option. That's enough.
    options = parser.parse_args()
    assert options.verbose == False


def test_BuiReader():
    filepath = os.path.join(rain_files_dir, "reeks_10jr_1955002 19550517124500")
    bui = BuiReader(filepath)
    assert bui.filepath == os.path.join(
        rain_files_dir, "reeks_10jr_1955002 19550517124500"
    )
