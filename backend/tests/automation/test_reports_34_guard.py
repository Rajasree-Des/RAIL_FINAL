"""Smoke guard: Report 3/4 processor surfaces remain stable."""

from __future__ import annotations

from app.automation.processing import report3_processor, report4_processor


def test_report3_processor_surface():
    assert report3_processor.PROCESSOR_NAME == "report3_top20_trains_processor"
    assert hasattr(report3_processor, "Report3Processor")


def test_report4_processor_surface():
    assert report4_processor.PROCESSOR_NAME == "report4_causewise_top10_processor"
    assert hasattr(report4_processor, "Report4Processor")
