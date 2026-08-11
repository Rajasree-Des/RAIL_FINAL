"""Unit tests for Report Vande Bharat (Report No. 18) registration."""

from __future__ import annotations

import csv
from pathlib import Path

from app.automation.formatting.artifact_titles import (
    ARTIFACT_DISPLAY_TITLES,
    build_artifact_main_title,
    is_artifact_title_row,
)
from app.automation.handlers.registry import HANDLER_REGISTRY, get_handler
from app.automation.processing.registry import PROCESSORS
from app.automation.processing.report18_processor import Report18Processor
from app.automation.report_keys import CANONICAL_KEYS, is_supported_report_key
from app.automation.report18_filters import REPORT18_FILE_STEM
from app.automation.reports import DEFAULT_CATALOG, REPORT_18, catalog
from app.automation.date_range import ReportDateRange
from datetime import date
from app.features.datasets.service import SUPPORTED_REPORT_IDS
from app.features.reports.slug_map import MANUAL_REPORT_SLUGS, PAGE_ID_TO_SLUG, resolve_manual_slug


class TestReport18Registration:
    def test_report18_in_canonical_keys(self):
        assert "report18" in CANONICAL_KEYS
        assert is_supported_report_key("report18")

    def test_report18_in_default_catalog_before_bottom_report(self):
        slugs = [r.slug for r in DEFAULT_CATALOG]
        assert slugs.count("report18") == 1
        assert slugs[-2] == "report18"
        assert slugs[-1] == "bottom-report"
        assert slugs[-3] == "report14"

    def test_catalog_instance_order(self):
        slugs = [r.slug for r in catalog.reports]
        assert slugs[-2] == "report18"
        assert slugs[-1] == "bottom-report"
        assert len(slugs) == 11

    def test_handler_registered(self):
        assert "report18" in HANDLER_REGISTRY
        handler = get_handler("report18")
        assert handler.__class__.__name__ == "Report18Handler"

    def test_processor_registered(self):
        assert "report18" in PROCESSORS
        assert isinstance(PROCESSORS["report18"], Report18Processor)

    def test_manual_slug_and_page_id(self):
        assert "report18" in MANUAL_REPORT_SLUGS
        assert PAGE_ID_TO_SLUG["report18"] == "report18"
        assert resolve_manual_slug("report18") == "report18"

    def test_supported_dataset_id(self):
        assert "report18" in SUPPORTED_REPORT_IDS

    def test_portal_definition(self):
        assert REPORT_18.slug == "report18"
        assert REPORT_18.name == "Report Vande Bharat"
        assert "vandebharatreport" in REPORT_18.page_path
        assert REPORT_18.url_fragment == "mis_reports/vandebharatreport"


class TestReport18Processor:
    def test_writes_exact_artifact_names(self, tmp_path: Path):
        from app.automation.report18_detail_extract import REPORT18_FINAL_HEADERS

        csv_path = tmp_path / "vande_bharat_complaint_details.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(REPORT18_FINAL_HEADERS)
            row = [""] * len(REPORT18_FINAL_HEADERS)
            row[0] = "1"
            row[1] = "REF001"
            row[4] = "20834"
            row[15] = "VSKP-SC [VANDE BHARAT]"
            writer.writerow(row)
            row2 = list(row)
            row2[0] = "2"
            row2[1] = "REF002"
            writer.writerow(row2)

        processor = Report18Processor()
        result = processor.process(
            source_a_path=csv_path,
            report_slug="report18",
            column_selection={
                "run_id": "run-test",
                "date_from": "2026-08-10",
                "date_to": "2026-08-10",
            },
        )
        assert result.success
        assert result.excel_path
        assert result.pdf_path
        assert Path(result.excel_path).name == f"{REPORT18_FILE_STEM}.xlsx"
        assert Path(result.pdf_path).name == f"{REPORT18_FILE_STEM}.pdf"
        assert Path(result.excel_path).is_file()
        assert Path(result.pdf_path).is_file()
        assert result.processed_row_count == 2

    def test_fails_on_empty_table(self, tmp_path: Path):
        from app.automation.report18_detail_extract import REPORT18_FINAL_HEADERS

        csv_path = tmp_path / "empty.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(REPORT18_FINAL_HEADERS)

        result = Report18Processor().process(
            source_a_path=csv_path,
            report_slug="report18",
            column_selection={"run_id": "run-empty"},
        )
        assert not result.success
        assert "REPORT18_TABLE_MISSING" in (result.error or "")


class TestReport18DetailTransform:
    def test_maps_portal_headers_to_final_columns(self):
        from app.automation.report18_detail_extract import (
            REPORT18_FINAL_HEADERS,
            transform_detail_rows_to_final,
        )

        portal_rows = [
            {
                "S. No.": "1",
                "Ref. No.": "20260809010380",
                "Registration Date": "09-08-26 20:08",
                "Closing Date": "09-08-26 21:38",
                "Train/Station": "20708",
                "Channel": "A",
                "Type": "Catering & Vending Services",
                "Owning Zone": "SC",
                "Dept": "IRCTG",
                "SLA": "No",
                "Rating": "Unsatisfactory",
                "Status": "Closed",
                "Feedback Remark": "",
                "Next Station": "WL",
                "Contact Id": "9490795779",
                "Physical Coach No.": "251124",
                "Train Name For Report": "VSKP-SC [VANDE BHARAT]",
                "Complaint Description": "food was half cooked",
                "Remarks": "apologized, assured for improvement",
                "User Id": "irc_south_central_zone",
            }
        ]
        headers, rows, source_headers = transform_detail_rows_to_final(portal_rows)
        assert headers == REPORT18_FINAL_HEADERS
        assert len(rows) == 1
        assert "Ref. No." in source_headers
        out = dict(zip(headers, rows[0], strict=True))
        assert out["Sl No"] == "1"
        assert out["complaintRefNo"] == "20260809010380"
        assert out["createdOn"] == "09-08-26 20:08"
        assert out["modifiedOn"] == "09-08-26 21:38"
        assert out["trainStation"] == "20708"
        assert out["channelType"] == "A"
        assert out["compTypeName"] == "Catering & Vending Services"
        assert out["ownZoneCode"] == "SC"
        assert out["deptCode"] == "IRCTG"
        assert out["sla"] == "No"
        assert out["rating"] == "Unsatisfactory"
        assert out["status"] == "Closed"
        assert out["restStation"] == "WL"
        assert out["contactNo"] == "9490795779"
        assert out["physicalCoachNo"] == "251124"
        assert out["trainNameForReport"] == "VSKP-SC [VANDE BHARAT]"
        assert out["complaintDesc"] == "food was half cooked"
        assert out["userid"] == "irc_south_central_zone"


class TestReport18GrandTotalDetection:
    def test_intermediate_train_total_is_not_grand_total(self):
        from app.automation.report18_detail_extract import is_grand_total_row

        received_idx = 5
        intermediate = ["SCR", "HYB", "VSKP-SC", "20703", "TOTAL", "3"]
        grand = ["South Central Railway", "TOTAL", "TOTAL", "TOTAL", "TOTAL", "11"]

        assert not is_grand_total_row(intermediate, received_idx)
        assert is_grand_total_row(grand, received_idx)

    def test_grand_total_requires_at_least_three_total_labels(self):
        from app.automation.report18_detail_extract import count_grand_total_labels

        received_idx = 5
        two_labels = ["SCR", "HYB", "20703", "Catering", "TOTAL", "1"]
        assert count_grand_total_labels(two_labels, received_idx) == 1
        assert count_grand_total_labels(
            ["SCR", "TOTAL", "TOTAL", "TOTAL", "TOTAL", "11"], received_idx
        ) == 4


class TestReport18PaginationAndReconciliation:
    def test_dedupe_preserves_order_and_removes_duplicates(self):
        from app.automation.report18_detail_extract import dedupe_portal_rows_by_ref

        page1 = [
            {"Ref. No.": "2026081012056", "Status": "Closed"},
            {"Ref. No.": "2026081010651", "Status": "Closed"},
        ]
        page2 = [
            {"Ref. No.": "2026081010651", "Status": "Closed"},
            {"Ref. No.": "2026081010001", "Status": "Closed"},
        ]
        merged = dedupe_portal_rows_by_ref(page1 + page2)
        refs = [row["Ref. No."] for row in merged]
        assert refs == ["2026081012056", "2026081010651", "2026081010001"]

    def test_reconciliation_passes_when_counts_match(self):
        from app.automation.report18_detail_extract import reconcile_detail_counts

        ok, err = reconcile_detail_counts(11, 11, modal_total=11)
        assert ok
        assert err is None

    def test_reconciliation_fails_on_mismatch(self):
        from app.automation.report18_detail_extract import reconcile_detail_counts

        ok, err = reconcile_detail_counts(11, 10, modal_total=11)
        assert not ok
        assert err is not None
        assert "aggregate=11" in err
        assert "details=10" in err

    def test_zero_aggregate_accepts_empty_details(self):
        from app.automation.report18_detail_extract import reconcile_detail_counts

        ok, err = reconcile_detail_counts(0, 0)
        assert ok
        assert err is None


class TestReport18AggregateTableWait:
    def test_aggregate_ready_requires_populated_rows(self):
        from app.automation.report18_detail_extract import is_aggregate_table_ready

        assert not is_aggregate_table_ready(None)
        assert not is_aggregate_table_ready({"ready": False, "dataRowCount": 0})
        assert not is_aggregate_table_ready({"ready": True, "dataRowCount": 0})
        assert is_aggregate_table_ready({"ready": True, "dataRowCount": 1})
        assert is_aggregate_table_ready({"ready": True, "dataRowCount": 16}, min_data_rows=1)


class TestReport18Titles:
    def test_artifact_display_title(self):
        assert ARTIFACT_DISPLAY_TITLES["report18"] == "VB RAILMADAD REPORT - SCR"

    def test_build_title_includes_date(self):
        dr = ReportDateRange(date_from=date(2026, 8, 4), date_to=date(2026, 8, 4))
        title = build_artifact_main_title("report18", dr)
        assert title.startswith("VB RAILMADAD REPORT - SCR")
        assert is_artifact_title_row([title])


class TestReport18ProcessorReconciliation:
    def test_fails_when_summary_total_mismatch(self, tmp_path: Path):
        from app.automation.report18_detail_extract import (
            REPORT18_FINAL_HEADERS,
            REPORT18_SUMMARY_META_FILENAME,
        )

        csv_path = tmp_path / "vande_bharat_complaint_details.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(REPORT18_FINAL_HEADERS)
            row = [""] * len(REPORT18_FINAL_HEADERS)
            row[0] = "1"
            row[1] = "REF001"
            writer.writerow(row)

        meta_path = tmp_path / REPORT18_SUMMARY_META_FILENAME
        meta_path.write_text('{"summary_total": 11, "detail_excel_rows": 1}', encoding="utf-8")

        result = Report18Processor().process(
            source_a_path=csv_path,
            report_slug="report18",
            column_selection={
                "run_id": "run-reconcile",
                "date_from": "2026-08-10",
                "date_to": "2026-08-10",
            },
        )
        assert not result.success
        assert "vande_bharat_detail_reconciliation_failed" in (result.error or "")
        assert "aggregate=11" in (result.error or "")
        assert "details=1" in (result.error or "")


def _count_pdf_pages(pdf_path: Path) -> int:
    raw = pdf_path.read_bytes().decode("latin-1", errors="ignore")
    return raw.count("/Type /Page") - raw.count("/Type /Pages")


class TestReport18PdfLayout:
    def test_pdf_is_single_page_with_all_columns(self, tmp_path: Path):
        from app.automation.report18_detail_extract import (
            REPORT18_FINAL_HEADERS,
            REPORT18_SUMMARY_META_FILENAME,
        )

        csv_path = tmp_path / "vande_bharat_complaint_details.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(REPORT18_FINAL_HEADERS)
            for idx in range(1, 16):
                row = [""] * len(REPORT18_FINAL_HEADERS)
                row[0] = str(idx)
                row[1] = f"2026080901038{idx}"
                row[2] = "09-08-26 20:08"
                row[3] = "09-08-26 21:38"
                row[4] = "20708"
                row[6] = "Catering & Vending Services"
                row[17] = (
                    "Passenger reported that food served was half cooked and cold during the journey."
                )
                row[18] = "Staff apologized and assured improvement in catering quality."
                row[19] = "irc_south_central_zone"
                writer.writerow(row)

        meta_path = tmp_path / REPORT18_SUMMARY_META_FILENAME
        meta_path.write_text('{"summary_total": 15}', encoding="utf-8")

        result = Report18Processor().process(
            source_a_path=csv_path,
            report_slug="report18",
            column_selection={
                "run_id": "run-pdf-layout",
                "date_from": "2026-08-10",
                "date_to": "2026-08-10",
            },
        )
        assert result.success
        assert result.pdf_path
        pdf_path = Path(result.pdf_path)
        assert pdf_path.is_file()
        assert _count_pdf_pages(pdf_path) == 1
        assert len(result.output_columns or []) == len(REPORT18_FINAL_HEADERS)


class TestReport18RemarksTruncation:
    def test_long_remarks_limited_to_three_pdf_lines(self):
        from app.automation.processing.report18_processor import _truncate_remarks_for_pdf

        long_text = (
            "Dear Sir, Sorry for the inconvenience caused. "
            "Staff attended immediately and cleaned the coach thoroughly. "
            "Passenger was offered assistance and assured of better service. "
            "Further action has been taken with the concerned department. "
            "We regret the discomfort experienced during the journey."
        )
        truncated = _truncate_remarks_for_pdf(
            long_text,
            col_width_pt=76,
            font_size=6.8,
            max_lines=5,
        )
        assert truncated
        assert truncated.count("\n") <= 4
        assert truncated.endswith("...")
        assert len(truncated) < len(long_text)

    def test_short_remarks_are_unchanged(self):
        from app.automation.processing.report18_processor import _truncate_remarks_for_pdf

        short = "Coach cleaned and passenger satisfied."
        assert _truncate_remarks_for_pdf(short, col_width_pt=76, font_size=6.8) == short
