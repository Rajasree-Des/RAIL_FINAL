"""Unit tests for Report 10-13 (Comprehensive Reports)."""

import pytest
from pathlib import Path

from app.automation.report_keys import (
    CANONICAL_KEYS,
    canonicalize_report_key,
    is_supported_report_key,
)
from app.automation.reports import (
    DEFAULT_CATALOG,
    REPORT_10_13_COMPREHENSIVE,
    catalog,
)
from app.automation.handlers.registry import HANDLER_REGISTRY, get_handler
from app.automation.processing.registry import PROCESSORS
from app.automation.processing.comprehensive1013_processor import Comprehensive1013Processor
from app.automation.comprehensive1013_filters import (
    COMPREHENSIVE_1013_SECTION_IDS,
    SECTION_CONFIGS,
    SectionConfig,
    get_all_section_configs,
    get_section_config_by_id,
    get_section_filters,
)
from app.automation.processing.comprehensive_output_columns import (
    ADDITIVE_COLUMNS,
    COMPREHENSIVE_COLUMN_IDS,
    COMPREHENSIVE_COLUMN_LABELS,
    NON_ADDITIVE_COLUMNS,
    column_labels,
    default_column_ids,
    normalize_header_to_column_id,
)


class TestReportRegistration:
    """Tests for report registration in catalog and registries."""

    def test_comprehensive_in_canonical_keys(self):
        assert "comprehensive-10-13" in CANONICAL_KEYS

    def test_section_ids_in_canonical_keys(self):
        assert "report10_cw" in CANONICAL_KEYS
        assert "report11_security" in CANONICAL_KEYS
        assert "report12_punctuality" in CANONICAL_KEYS
        assert "report13_electrical" in CANONICAL_KEYS

    def test_is_supported_report_key(self):
        assert is_supported_report_key("comprehensive-10-13")
        assert is_supported_report_key("report10_cw")

    def test_canonicalize_comprehensive_key(self):
        assert canonicalize_report_key("comprehensive-10-13") == "comprehensive-10-13"

    def test_comprehensive_in_default_catalog(self):
        slugs = [r.slug for r in DEFAULT_CATALOG]
        assert "comprehensive-10-13" in slugs

    def test_comprehensive_report_definition(self):
        assert REPORT_10_13_COMPREHENSIVE.slug == "comprehensive-10-13"
        assert REPORT_10_13_COMPREHENSIVE.name == "Report 10-13 (Comprehensive Reports)"
        assert REPORT_10_13_COMPREHENSIVE.page_path == "/mis_reports/report1"


class TestHandlerRegistration:
    """Tests for handler registration."""

    def test_handler_registered(self):
        assert "comprehensive-10-13" in HANDLER_REGISTRY

    def test_get_handler_returns_instance(self):
        handler = get_handler("comprehensive-10-13")
        assert handler is not None
        assert handler.__class__.__name__ == "Comprehensive1013Handler"


class TestProcessorRegistration:
    """Tests for processor registration."""

    def test_processor_registered(self):
        assert "comprehensive-10-13" in PROCESSORS

    def test_processor_has_process_method(self):
        processor = PROCESSORS.get("comprehensive-10-13")
        assert processor is not None
        assert hasattr(processor, "process")


class TestSectionConfigs:
    """Tests for section configuration definitions."""

    def test_four_sections_defined(self):
        configs = get_all_section_configs()
        assert len(configs) == 4

    def test_section_ids_list(self):
        assert COMPREHENSIVE_1013_SECTION_IDS == [
            "report10_cw",
            "report11_security",
            "report12_punctuality",
            "report13_electrical",
        ]

    def test_section_config_structure(self):
        for config in SECTION_CONFIGS:
            assert isinstance(config, SectionConfig)
            assert config.section_id
            assert config.name
            assert config.section_title
            assert config.department
            assert config.mode
            assert config.complaint_type

    def test_get_section_config_by_id(self):
        config = get_section_config_by_id("report10_cw")
        assert config is not None
        assert config.section_id == "report10_cw"
        assert config.name == "Report 10 - C&W"
        assert config.department == "Carriage & Wagon"
        assert config.mode == "Train"

    def test_get_section_config_by_id_not_found(self):
        config = get_section_config_by_id("invalid_section")
        assert config is None

    def test_report10_cw_config(self):
        config = get_section_config_by_id("report10_cw")
        assert config.department == "Carriage & Wagon"
        assert config.mode == "Train"
        assert config.complaint_type == "ALL"

    def test_report11_security_config(self):
        config = get_section_config_by_id("report11_security")
        assert config.department == "ALL"
        assert config.mode == "ALL"
        assert config.complaint_type == "Security-Train"

    def test_report12_punctuality_config(self):
        config = get_section_config_by_id("report12_punctuality")
        assert config.department == "ALL"
        assert config.mode == "ALL"
        assert config.complaint_type == "Punctuality-Train"

    def test_report13_electrical_config(self):
        config = get_section_config_by_id("report13_electrical")
        assert config.department == "ALL"
        assert config.mode == "ALL"
        assert config.complaint_type == "Electrical Equipment-Train"


class TestSectionFilters:
    """Tests for section filter generation."""

    def test_get_section_filters_returns_list(self):
        config = get_section_config_by_id("report10_cw")
        filters = get_section_filters(config)
        assert isinstance(filters, list)
        assert len(filters) > 0

    def test_all_sections_have_zone_filter(self):
        for config in SECTION_CONFIGS:
            filters = get_section_filters(config)
            zone_filter = next(
                (f for f in filters if f.name == "zone"),
                None,
            )
            assert zone_filter is not None
            assert zone_filter.value == "South Central Railway"

    def test_all_sections_have_division_all(self):
        for config in SECTION_CONFIGS:
            filters = get_section_filters(config)
            div_filter = next(
                (f for f in filters if f.name == "division"),
                None,
            )
            assert div_filter is not None
            assert div_filter.value == "ALL"

    def test_all_sections_have_view_division_wise(self):
        for config in SECTION_CONFIGS:
            filters = get_section_filters(config)
            view_filter = next(
                (f for f in filters if f.name == "view"),
                None,
            )
            assert view_filter is not None
            assert view_filter.value == "Division Wise"

    def test_report10_specific_filters(self):
        config = get_section_config_by_id("report10_cw")
        filters = get_section_filters(config)

        dept_filter = next((f for f in filters if f.name == "department"), None)
        assert dept_filter is not None
        assert dept_filter.value == "Carriage & Wagon"

        mode_filter = next((f for f in filters if f.name == "mode"), None)
        assert mode_filter is not None
        assert mode_filter.value == "Train"


class TestOutputColumns:
    """Tests for output column definitions."""

    def test_eleven_columns_defined(self):
        assert len(COMPREHENSIVE_COLUMN_IDS) == 11

    def test_column_ids_list(self):
        expected = [
            "sno",
            "division",
            "opening_balance",
            "received",
            "share_percent",
            "closed",
            "closing_balance",
            "disposal_percent",
            "avg_disposal_time",
            "avg_rating",
            "avg_pendency_time",
        ]
        assert COMPREHENSIVE_COLUMN_IDS == expected

    def test_all_columns_have_labels(self):
        for col_id in COMPREHENSIVE_COLUMN_IDS:
            assert col_id in COMPREHENSIVE_COLUMN_LABELS
            assert COMPREHENSIVE_COLUMN_LABELS[col_id]

    def test_default_column_ids(self):
        defaults = default_column_ids()
        assert defaults == COMPREHENSIVE_COLUMN_IDS

    def test_column_labels_function(self):
        labels = column_labels(["sno", "division", "received"])
        assert labels == ["S.No.", "Division", "Received"]

    def test_additive_columns(self):
        assert "opening_balance" in ADDITIVE_COLUMNS
        assert "received" in ADDITIVE_COLUMNS
        assert "closed" in ADDITIVE_COLUMNS
        assert "closing_balance" in ADDITIVE_COLUMNS

    def test_non_additive_columns(self):
        assert "disposal_percent" in NON_ADDITIVE_COLUMNS
        assert "avg_disposal_time" in NON_ADDITIVE_COLUMNS
        assert "avg_rating" in NON_ADDITIVE_COLUMNS
        assert "avg_pendency_time" in NON_ADDITIVE_COLUMNS


class TestHeaderNormalization:
    """Tests for header to column ID normalization."""

    def test_normalize_standard_headers(self):
        assert normalize_header_to_column_id("S.No.") == "sno"
        assert normalize_header_to_column_id("Division") == "division"
        assert normalize_header_to_column_id("Received") == "received"
        assert normalize_header_to_column_id("% Share") == "share_percent"
        assert normalize_header_to_column_id("% Disposal") == "disposal_percent"

    def test_normalize_alias_headers(self):
        assert normalize_header_to_column_id("Sl.No.") == "sno"
        assert normalize_header_to_column_id("Organisation") == "division"
        assert normalize_header_to_column_id("Opening") == "opening_balance"
        assert normalize_header_to_column_id("Closing") == "closing_balance"

    def test_normalize_case_insensitive(self):
        assert normalize_header_to_column_id("division") == "division"
        assert normalize_header_to_column_id("DIVISION") == "division"

    def test_normalize_unknown_header(self):
        assert normalize_header_to_column_id("Unknown Column") is None


class TestComprehensiveProjection:
    def test_project_columns_uses_organisation_when_division_empty(self):
        processor = Comprehensive1013Processor()
        raw_headers = [
            "S.No.",
            "Division",
            "Organisation",
            "Opening Balance",
            "Received",
        ]
        data_rows = [
            {
                "S.No.": "1",
                "Division": "",
                "Organisation": "SECUNDERABAD DIVISION (South Central Railway)",
                "Opening Balance": "0",
                "Received": "10",
            }
        ]
        selected = ["sno", "division", "opening_balance", "received"]
        headers, rows = processor._project_columns(raw_headers, data_rows, selected)
        assert headers == ["S.No.", "Division", "Opening Balance", "Received"]
        assert rows[0][1] == "SECUNDERABAD DIVISION (South Central Railway)"

    def test_project_columns_prefers_division_over_empty_organisation(self):
        processor = Comprehensive1013Processor()
        raw_headers = ["S.No.", "Division", "Organisation", "Received"]
        data_rows = [
            {
                "S.No.": "1",
                "Division": "HYDERABAD DIVISION (South Central Railway)",
                "Organisation": "",
                "Received": "5",
            }
        ]
        selected = ["sno", "division", "received"]
        _, rows = processor._project_columns(raw_headers, data_rows, selected)
        assert rows[0][1] == "HYDERABAD DIVISION (South Central Railway)"


class TestCatalogIntegrity:
    """Tests to ensure Reports 1-6 remain unchanged."""

    def test_original_six_reports_present(self):
        slugs = [r.slug for r in catalog.reports]
        assert "report1" in slugs
        assert "division" in slugs
        assert "train-no" in slugs
        assert "types" in slugs
        assert "scr-train" in slugs
        assert "scr-station" in slugs

    def test_catalog_has_ten_reports(self):
        assert len(catalog.reports) == 10

    def test_first_report_unchanged(self):
        report = catalog.first_report()
        assert report.slug == "report1"

    def test_report18_is_last(self):
        reports = catalog.reports
        assert reports[-1].slug == "report18"
        assert reports[-2].slug == "report14"
        assert reports[-3].slug == "comprehensive-10-13"


@pytest.mark.asyncio
async def test_submit_section_waits_for_delayed_fingerprint_change():
    """Punctuality often loads after generate_report soft-returns; keep waiting."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.automation.handlers.comprehensive1013_handler import Comprehensive1013Handler

    handler = Comprehensive1013Handler()
    page = MagicMock()
    page.wait_for_load_state = AsyncMock()
    session = MagicMock()
    report_root = MagicMock()
    section = get_section_config_by_id("report12_punctuality")
    assert section is not None

    handler.ensure_mis_page = AsyncMock(side_effect=lambda page, session, ctx="", **kwargs: page)
    handler.filter_service = MagicMock()
    handler.filter_service.get_report_root = AsyncMock(return_value=report_root)
    handler._apply_filters_fast = AsyncMock(
        return_value={
            "view": "Division Wise",
            "zone": "South Central Railway",
            "type": section.complaint_type or "",
        }
    )
    handler._verify_core_filters = MagicMock()
    handler.generator = MagicMock()
    handler.generator.generate_report = AsyncMock()
    handler.generator.verify_report_displayed = AsyncMock(return_value=True)

    with (
        patch(
            "app.automation.handlers.comprehensive1013_handler.apply_previous_from_date",
            new=AsyncMock(),
        ),
        patch(
            "app.automation.handlers.comprehensive1013_handler.log_phase1_submit_clicked",
        ),
        patch(
            "app.automation.handlers.comprehensive1013_handler.get_run_context",
            return_value=None,
        ),
        patch(
            "app.automation.handlers.comprehensive1013_handler.table_fingerprint",
            new=AsyncMock(side_effect=["OLD##sec", "NEW##pun"]),
        ),
        patch(
            "app.automation.handlers.comprehensive1013_handler.wait_for_table_refresh",
            new=AsyncMock(return_value=True),
        ) as wait_refresh,
    ):
        result_root = await handler._submit_section_once(
            page, session, REPORT_10_13_COMPREHENSIVE, section, attempt=1
        )

    assert result_root is report_root
    wait_refresh.assert_awaited()
    assert wait_refresh.await_args.kwargs.get("timeout_seconds") == 30.0
    handler.generator.generate_report.assert_awaited_once()
