"""Unit tests for report catalog."""

from app.automation.reports import (
    DEFAULT_CATALOG,
    REPORT_1,
    REPORT_2,
    REPORT_3_TRAIN_NO,
    REPORT_4_TYPES,
    REPORT_5_SCR_TRAIN,
    REPORT_6_SCR_STATION,
    REPORT_9,
    REPORT_10_13_COMPREHENSIVE,
    REPORT_14,
    REPORT_18,
    ReportCatalog,
    catalog,
)


def test_catalog_contains_all_reports():
    slugs = [report.slug for report in catalog.reports]
    assert slugs == [
        "report1",
        "division",
        "train-no",
        "types",
        "scr-train",
        "scr-station",
        "report9",
        "comprehensive-10-13",
        "report14",
        "report18",
    ]


def test_default_catalog_order():
    assert DEFAULT_CATALOG == [
        REPORT_1,
        REPORT_2,
        REPORT_3_TRAIN_NO,
        REPORT_4_TYPES,
        REPORT_5_SCR_TRAIN,
        REPORT_6_SCR_STATION,
        REPORT_9,
        REPORT_10_13_COMPREHENSIVE,
        REPORT_14,
        REPORT_18,
    ]


def test_first_report_is_mis_report_1():
    report = catalog.first_report()
    assert report == REPORT_1
    assert report.slug == "report1"


def test_report_catalog_custom_list():
    custom = ReportCatalog([REPORT_1, REPORT_2])
    assert [r.slug for r in custom.reports] == ["report1", "division"]
