"""Unit tests for Report 14 (Watering Complaints)."""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.handlers.registry import HANDLER_REGISTRY, get_handler
from app.automation.handlers.report14_handler import Report14Handler
from app.automation.processing.registry import PROCESSORS
from app.automation.processing.report14_processor import Report14Processor
from app.automation.report_keys import CANONICAL_KEYS, is_supported_report_key
from app.automation.report14_filters import (
    SECTION_ORDER,
    SOURCE_PREVIOUS,
    SOURCE_UPCOMING,
    filters_for_source,
    filters_previous,
    filters_upcoming,
)
from app.automation.reports import DEFAULT_CATALOG, REPORT_14, catalog
from app.features.datasets.service import SUPPORTED_REPORT_IDS
from app.features.reports.slug_map import MANUAL_REPORT_SLUGS, PAGE_ID_TO_SLUG, resolve_manual_slug


class TestReport14Registration:
    def test_report14_in_canonical_keys(self):
        assert "report14" in CANONICAL_KEYS
        assert is_supported_report_key("report14")

    def test_report14_in_default_catalog_before_report18(self):
        slugs = [r.slug for r in DEFAULT_CATALOG]
        assert slugs.count("report14") == 1
        assert slugs[-3] == "report14"
        assert slugs[-4] == "comprehensive-10-13"
        assert slugs[-2] == "report18"
        assert slugs[-1] == "bottom-report"

    def test_catalog_instance_order(self):
        slugs = [r.slug for r in catalog.reports]
        assert slugs[-3] == "report14"
        assert "report14" in slugs
        assert len(slugs) == 11

    def test_handler_registered(self):
        assert "report14" in HANDLER_REGISTRY
        handler = get_handler("report14")
        assert handler.__class__.__name__ == "Report14Handler"

    def test_processor_registered(self):
        assert "report14" in PROCESSORS
        assert isinstance(PROCESSORS["report14"], Report14Processor)

    def test_manual_slug_and_page_id(self):
        assert "report14" in MANUAL_REPORT_SLUGS
        assert PAGE_ID_TO_SLUG["report14"] == "report14"
        assert resolve_manual_slug("report14") == "report14"

    def test_supported_dataset_id(self):
        assert "report14" in SUPPORTED_REPORT_IDS

    def test_portal_definition(self):
        assert REPORT_14.slug == "report14"
        assert "Watering" in REPORT_14.name
        # Live form is report22 after menu; report11 URL alone is a blank shell.
        assert "mis_reports" in REPORT_14.page_path
        assert REPORT_14.url_fragment


class TestReport14Filters:
    def test_two_sources(self):
        assert len(SECTION_ORDER) == 2
        assert SECTION_ORDER[0] is SOURCE_PREVIOUS
        assert SECTION_ORDER[1] is SOURCE_UPCOMING

    def test_filters_share_zone(self):
        prev = filters_previous()
        up = filters_upcoming()
        prev_map = {f.name: f.value for f in prev}
        up_map = {f.name: f.value for f in up}
        assert prev_map.get("zone") == up_map.get("zone") == "South Central Railway"
        assert prev_map.get("view") == up_map.get("view") == "Division Wise"
        assert any(f.name == "output" for f in prev)
        assert prev_map["output"] == "Previous Watering Point"
        assert up_map["output"] == "Upcoming Watering Point"
        assert all(f.required for f in prev if f.name in {"zone", "view", "output"})

    def test_filters_for_source(self):
        custom = filters_for_source("Previous Watering Point")
        assert any(f.name == "zone" for f in custom)

    def test_verify_core_filters_rejects_blank_zone(self):
        from app.automation.handlers.report14_handler import Report14Handler
        from app.automation.filters import FilterError

        with pytest.raises(FilterError, match="ZONE_FILTER"):
            Report14Handler._verify_core_filters(
                {"zone": "", "view": "Division Wise", "output": "Previous Watering Point"},
                cfg=SOURCE_PREVIOUS,
                report_slug="report14",
            )

    def test_verify_core_filters_rejects_train_type_view(self):
        from app.automation.handlers.report14_handler import Report14Handler
        from app.automation.filters import FilterError

        with pytest.raises(FilterError, match="VIEW_FILTER"):
            Report14Handler._verify_core_filters(
                {
                    "zone": "South Central Railway",
                    "view": "Train Type Wise",
                    "output": "Previous Watering Point",
                },
                cfg=SOURCE_PREVIOUS,
                report_slug="report14",
            )

    def test_verify_core_filters_accepts_scr_and_division(self):
        from app.automation.handlers.report14_handler import Report14Handler

        Report14Handler._verify_core_filters(
            {
                "zone": "South Central Railway",
                "view": "Division Wise",
                "output": "Previous Watering Point",
            },
            cfg=SOURCE_PREVIOUS,
            report_slug="report14",
        )


class TestReport14Processor:
    def _write_source_csv(self, path: Path, rows: list[list[str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(rows)

    def test_side_by_side_merge_by_division(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from app.automation.processing import report14_processor as r14mod

        monkeypatch.setattr(r14mod.config, "output_excel_dir", str(tmp_path / "excel"))
        monkeypatch.setattr(r14mod.config, "output_pdf_dir", str(tmp_path / "pdf"))

        run_dir = tmp_path / "extracted" / "report14" / "run1"
        run_dir.mkdir(parents=True)

        prev_csv = run_dir / "previous_watering.csv"
        up_csv = run_dir / "upcoming_watering.csv"
        self._write_source_csv(
            prev_csv,
            [
                ["Division", "Received", "% Share", "Average Rating"],
                ["SECUNDERABAD DIVISION", "4", "57.14", "Satisfactory"],
                ["HYDERABAD DIVISION", "2", "28.57", "UnSatisfactory"],
                ["NANDED DIVISION", "1", "14.29", "Nil"],
                ["Total", "7", "100", "Satisfactory"],
            ],
        )
        self._write_source_csv(
            up_csv,
            [
                ["Division", "Received", "% Share", "Average Rating"],
                ["SECUNDERABAD DIVISION", "5", "71.43", "UnSatisfactory"],
                ["HYDERABAD DIVISION", "1", "14.29", "Nil"],
                ["NANDED DIVISION", "1", "14.29", "Nil"],
                ["Total", "7", "100", "UnSatisfactory"],
            ],
        )

        index_path = run_dir / "report14_combined_index.csv"
        with index_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["source_id", "section_title", "watering_point", "csv_path", "row_count", "status", "error"]
            )
            writer.writerow(
                [
                    "previous_watering",
                    "Previous",
                    "Previous Watering Point",
                    str(prev_csv),
                    2,
                    "success",
                    "",
                ]
            )
            writer.writerow(
                [
                    "upcoming_watering",
                    "Upcoming",
                    "Upcoming Watering Point",
                    str(up_csv),
                    2,
                    "success",
                    "",
                ]
            )

        processor = Report14Processor()
        result = processor.process(
            source_a_path=index_path,
            report_slug="report14",
            column_selection={
                "run_id": "run1",
                "date_from": "2026-08-01",
                "date_to": "2026-08-03",
            },
        )
        assert result.success is True
        assert result.excel_path and Path(result.excel_path).is_file()
        assert result.pdf_path and Path(result.pdf_path).is_file()
        assert result.processed_row_count == 3  # three divisions aligned by key

        processor = Report14Processor()
        prev_data, prev_headers = processor._read_csv(prev_csv)
        up_data, up_headers = processor._read_csv(up_csv)
        prev_data, prev_total = processor._split_total_row(prev_data)
        up_data, up_total = processor._split_total_row(up_data)
        headers, rows = processor._merge_by_division(
            prev_data,
            prev_headers,
            up_data,
            up_headers,
            prev_total=prev_total,
            up_total=up_total,
        )
        assert headers[1] == "Division"
        assert rows[0][1] == "SECUNDERABAD DIVISION"
        assert rows[0][2] == "4"
        assert rows[0][5] == "5"
        assert rows[-1][1] == "Total"
        assert rows[-1][2] == "7"
        assert rows[-1][5] == "7"

    def test_missing_source_fails(self, tmp_path: Path):
        index_path = tmp_path / "report14_combined_index.csv"
        with index_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["source_id", "section_title", "watering_point", "csv_path", "row_count", "status", "error"]
            )
            writer.writerow(
                ["previous_watering", "Previous", "Previous", "", 0, "failed", "missing"]
            )
            writer.writerow(
                ["upcoming_watering", "Upcoming", "Upcoming", "", 0, "failed", "missing"]
            )
        result = Report14Processor().process(
            source_a_path=index_path,
            report_slug="report14",
        )
        assert result.success is False
        assert "REPORT14_TABLE_MISSING" in (result.error or "")


class TestReport14HandlerDates:
    @pytest.mark.asyncio
    async def test_handler_applies_same_date_range_to_both_sources(self, tmp_path: Path):
        handler = Report14Handler()
        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        page.wait_for_selector = AsyncMock()
        session = MagicMock()
        report = REPORT_14

        applied_sources: list[str] = []

        async def _fake_filters(*_a, cfg=None, **_k):
            if cfg is not None:
                applied_sources.append(cfg.source_id)
            return {
                "zone": "South Central Railway",
                "view": "Division Wise",
                "division": "ALL",
                "output": cfg.watering_point if cfg else "Previous Watering Point",
            }

        with (
            patch.object(handler, "ensure_mis_page", new=AsyncMock(side_effect=lambda p, s, *a, **k: p)),
            patch(
                "app.automation.handlers.report14_handler.navigate_report14_via_menu",
                new=AsyncMock(return_value=page),
            ),
            patch.object(handler.navigation, "navigate_to_report", new=AsyncMock()) as mock_url_nav,
            patch.object(
                handler.filter_service,
                "get_report_root",
                new=AsyncMock(return_value=MagicMock()),
            ),
            patch.object(
                handler,
                "_apply_and_verify_filters",
                new=AsyncMock(side_effect=_fake_filters),
            ),
            patch(
                "app.automation.handlers.report14_handler.apply_previous_from_date",
                new=AsyncMock(),
            ),
            patch(
                "app.automation.handlers.report14_handler.log_phase1_submit_clicked",
            ),
            patch.object(handler.generator, "generate_report", new=AsyncMock()),
            patch.object(
                handler.generator,
                "verify_report_displayed",
                new=AsyncMock(return_value=True),
            ),
            patch.object(handler, "click_received_twice", new=AsyncMock()),
            patch(
                "app.automation.handlers.report14_handler.TableExtractor"
            ) as mock_extractor_cls,
            patch.object(
                handler,
                "finalize_after_extract",
                new=AsyncMock(
                    return_value=MagicMock(
                        ingestion_success=True,
                        processing_success=True,
                        excel_path="/x.xlsx",
                        pdf_path="/x.pdf",
                        model_copy=lambda **kw: MagicMock(
                            ingestion_success=True,
                            processing_success=True,
                            excel_path="/x.xlsx",
                            pdf_path="/x.pdf",
                            error=None,
                        ),
                    )
                ),
            ),
            patch(
                "app.automation.handlers.report14_handler.get_run_context",
                return_value=None,
            ),
            patch(
                "app.automation.handlers.report14_handler.config",
            ) as mock_cfg,
        ):
            mock_cfg.extracted_data_dir = str(tmp_path / "extracted")
            extractor = mock_extractor_cls.return_value
            extractor.extract_table_data_by_headers = AsyncMock(
                return_value=[
                    ["Division", "Received"],
                    ["SC", "10"],
                ]
            )
            extractor.extract_table_data = AsyncMock(return_value=[])

            result = await handler.execute(page, session, report)

        assert applied_sources == ["previous_watering", "upcoming_watering"]
        assert result is not None
        mock_url_nav.assert_not_awaited()
