"""Tests for Phase 8 process_report kwarg routing."""

from __future__ import annotations

import inspect

from app.automation.processing.registry import PROCESSORS


def test_report1_processor_accepts_column_selection():
    proc = PROCESSORS["report1"]
    assert "column_selection" in inspect.signature(proc.process).parameters


def test_train_no_processor_does_not_accept_column_selection():
    proc = PROCESSORS["train-no"]
    assert "column_selection" not in inspect.signature(proc.process).parameters


def test_types_processor_does_not_accept_column_selection():
    proc = PROCESSORS["types"]
    assert "column_selection" not in inspect.signature(proc.process).parameters


def test_scr_train_processor_does_not_accept_column_selection():
    proc = PROCESSORS["scr-train"]
    assert "column_selection" not in inspect.signature(proc.process).parameters


def test_scr_station_processor_does_not_accept_column_selection():
    proc = PROCESSORS["scr-station"]
    assert "column_selection" not in inspect.signature(proc.process).parameters


def test_division_processor_accepts_column_selection():
    proc = PROCESSORS["division"]
    assert "column_selection" in inspect.signature(proc.process).parameters
