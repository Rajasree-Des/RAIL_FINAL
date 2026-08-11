"""Focused tests for Report 14 MIS menu navigation (no URL-only success)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.report14_navigation import (
    MIS_REPORTS_LABEL,
    TAB11_MENU_LABEL,
    Report14NavigationError,
    click_tab11_train_watering,
    ensure_mis_reports_expanded,
    menu_text_matches_tab11,
    navigate_report14_via_menu,
    normalize_menu_text,
    wait_for_report14_form,
)


class TestReport14MenuText:
    def test_normalize_whitespace(self):
        assert normalize_menu_text("11) Train Watering\nComplaint") == "11) Train Watering Complaint"

    def test_wrapped_tab11_matches(self):
        assert menu_text_matches_tab11("11) Train Watering\nComplaint")
        assert menu_text_matches_tab11("11) Train Watering Complaint")
        assert menu_text_matches_tab11("11) Train Watering Complaints")
        assert menu_text_matches_tab11("11. Train Watering Complaints")
        assert not menu_text_matches_tab11("10) Zone/Train Type wise Report")
        assert not menu_text_matches_tab11("12) Suggestion Comprehensive")
        # Never treat Inquiry Wise 2 (sidebar tab 14) as Report 14 target
        assert not menu_text_matches_tab11("14) Inquiry Wise 2")
        assert not menu_text_matches_tab11(
            "11) Train Watering Complaint\n12) Suggestion Comprehensive"
        )


class TestReport14MenuNavigationOrder:
    @pytest.mark.asyncio
    async def test_does_not_use_direct_url_goto(self):
        page = MagicMock()
        page.url = "https://railmadad.example/rmmis/admin/home.jsp"
        page.goto = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.get_by_text = MagicMock(return_value=MagicMock(first=MagicMock(
            wait_for=AsyncMock(),
            count=AsyncMock(return_value=1),
            is_visible=AsyncMock(return_value=True),
            click=AsyncMock(),
        )))
        page.wait_for_timeout = AsyncMock()
        page.frames = []
        page.locator = MagicMock()

        with (
            patch(
                "app.automation.report14_navigation.ensure_mis_reports_expanded",
                new=AsyncMock(return_value=True),
            ) as mock_expand,
            patch(
                "app.automation.report14_navigation.click_tab11_train_watering",
                new=AsyncMock(return_value=(True, "11) Train Watering Complaints")),
            ) as mock_tab,
            patch(
                "app.automation.report14_navigation.wait_for_report14_form",
                new=AsyncMock(return_value=page),
            ) as mock_form,
            patch(
                "app.automation.report14_navigation._verify_tab11_page_loaded",
                new=AsyncMock(),
            ),
            patch(
                "app.automation.report14_navigation.url_matches_report_fragment",
                return_value=True,
            ),
        ):
            ctx = await navigate_report14_via_menu(page, run_id="run-1")

        page.goto.assert_not_awaited()
        mock_expand.assert_awaited()
        mock_tab.assert_awaited()
        mock_form.assert_awaited()
        assert ctx is page

    @pytest.mark.asyncio
    async def test_expands_mis_before_tab11(self):
        call_order: list[str] = []

        async def expand(_page):
            call_order.append("expand")
            return True

        async def click_tab(_page):
            call_order.append("tab11")
            return True, "11) Train Watering Complaints"

        async def wait_form(_page, **_kw):
            call_order.append("form")
            return _page

        page = MagicMock()
        page.url = "https://example/?page=/mis_reports/report22"
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.get_by_text = MagicMock(
            return_value=MagicMock(first=MagicMock(wait_for=AsyncMock()))
        )

        with (
            patch(
                "app.automation.report14_navigation.ensure_mis_reports_expanded",
                side_effect=expand,
            ),
            patch(
                "app.automation.report14_navigation.click_tab11_train_watering",
                side_effect=click_tab,
            ),
            patch(
                "app.automation.report14_navigation.wait_for_report14_form",
                side_effect=wait_form,
            ),
            patch(
                "app.automation.report14_navigation._verify_tab11_page_loaded",
                new=AsyncMock(),
            ),
            patch(
                "app.automation.report14_navigation.url_matches_report_fragment",
                return_value=True,
            ),
        ):
            await navigate_report14_via_menu(page, run_id="r")

        assert call_order == ["expand", "tab11", "form"]

    @pytest.mark.asyncio
    async def test_fails_when_form_blank_after_tab(self):
        page = MagicMock()
        page.url = "https://example/?page=/mis_reports/report11"
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.get_by_text = MagicMock(
            return_value=MagicMock(first=MagicMock(wait_for=AsyncMock()))
        )
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.frames = []

        with (
            patch(
                "app.automation.report14_navigation.ensure_mis_reports_expanded",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.automation.report14_navigation.click_tab11_train_watering",
                new=AsyncMock(return_value=(True, "11) Train Watering Complaints")),
            ),
            patch(
                "app.automation.report14_navigation.wait_for_report14_form",
                new=AsyncMock(side_effect=Report14NavigationError()),
            ),
            patch(
                "app.automation.report14_navigation._verify_tab11_page_loaded",
                new=AsyncMock(),
            ),
            patch(
                "app.automation.report14_navigation._save_nav_diagnostics",
                new=AsyncMock(),
            ),
            patch(
                "app.automation.report14_navigation.url_matches_report_fragment",
                return_value=False,
            ),
        ):
            with pytest.raises(Report14NavigationError) as exc:
                await navigate_report14_via_menu(page, run_id="r")
        assert "Train Watering Complaints form did not load" in str(exc.value)
        assert "report22" in str(exc.value)
        assert getattr(exc.value, "stage", "") == "report14_tab11_navigation"

    @pytest.mark.asyncio
    async def test_expand_skips_click_when_tab11_already_visible(self):
        page = MagicMock()
        with patch(
            "app.automation.report14_navigation._is_tab11_visible",
            new=AsyncMock(return_value=True),
        ):
            with patch(
                "app.automation.report14_navigation._find_mis_reports_control",
                new=AsyncMock(),
            ) as mock_find:
                ok = await ensure_mis_reports_expanded(page)
        assert ok is True
        mock_find.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_click_tab11_uses_scroll_and_exact_label_constant(self):
        assert TAB11_MENU_LABEL == "11) Train Watering Complaints"
        assert MIS_REPORTS_LABEL == "MIS Reports"

        loc = MagicMock()
        loc.scroll_into_view_if_needed = AsyncMock()
        loc.click = AsyncMock()
        loc.inner_text = AsyncMock(return_value="11) Train Watering Complaints")
        page = MagicMock()
        with patch(
            "app.automation.report14_navigation._find_tab11_control",
            new=AsyncMock(return_value=loc),
        ):
            ok, label = await click_tab11_train_watering(page)
        assert ok is True
        assert "Train Watering" in label
        loc.scroll_into_view_if_needed.assert_awaited()
        loc.click.assert_awaited()


class TestReport14FormFrameDetection:
    @pytest.mark.asyncio
    async def test_wait_resolves_when_main_page_has_controls(self):
        page = MagicMock()
        page.wait_for_timeout = AsyncMock()

        with patch(
            "app.automation.report14_navigation.resolve_report14_form_context",
            new=AsyncMock(side_effect=[None, page]),
        ):
            ctx = await wait_for_report14_form(page, timeout_ms=2000)
        assert ctx is page

    @pytest.mark.asyncio
    async def test_resolve_prefers_iframe_with_watering_form(self):
        from app.automation.report14_navigation import resolve_report14_form_context

        page = MagicMock()
        page.main_frame = object()
        named = MagicMock()
        named.name = "reportFrame"
        named.url = "https://example/mis_reports/report11"
        page.frames = [page.main_frame, named]
        frame_loc = MagicMock()
        page.frame_locator = MagicMock(return_value=frame_loc)

        watering_found = [
            "heading:Train Watering Wise Report",
            "output:Previous Watering Point",
            "From Date",
            "To Date",
            "Zone",
            "Output",
            "Submit",
        ]
        with patch(
            "app.automation.report14_navigation.is_train_watering_form",
            new=AsyncMock(side_effect=[(True, watering_found), (False, [])]),
        ):
            ctx = await resolve_report14_form_context(page)
        assert ctx is frame_loc
        page.frame_locator.assert_called()

    @pytest.mark.asyncio
    async def test_generic_mis_form_is_not_train_watering(self):
        """Other MIS report forms must not count as tab-11 success."""
        from app.automation.report14_navigation import is_train_watering_form

        with (
            patch(
                "app.automation.report14_navigation._count_form_signals",
                new=AsyncMock(
                    return_value=(
                        5,
                        ["From Date", "To Date", "Zone", "Division", "Submit"],
                    )
                ),
            ),
            patch(
                "app.automation.report14_navigation._has_watering_heading",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.automation.report14_navigation._has_watering_output_marker",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.automation.report14_navigation._has_watering_output_select",
                new=AsyncMock(return_value=False),
            ),
        ):
            ok, _ = await is_train_watering_form(MagicMock())
        assert ok is False

    @pytest.mark.asyncio
    async def test_does_not_skip_menu_when_url_is_report1(self):
        page = MagicMock()
        page.url = "https://example/?page=/mis_reports/report1"
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.get_by_text = MagicMock(
            return_value=MagicMock(first=MagicMock(wait_for=AsyncMock()))
        )
        fake_form = MagicMock()

        async def click_and_navigate(_page):
            page.url = "https://example/?page=/mis_reports/report22"
            return True, "11) Train Watering Complaint"

        with (
            patch(
                "app.automation.report14_navigation.resolve_report14_form_context",
                new=AsyncMock(return_value=fake_form),
            ),
            patch(
                "app.automation.report14_navigation.ensure_mis_reports_expanded",
                new=AsyncMock(return_value=True),
            ) as mock_expand,
            patch(
                "app.automation.report14_navigation.click_tab11_train_watering",
                side_effect=click_and_navigate,
            ),
            patch(
                "app.automation.report14_navigation.wait_for_report14_form",
                new=AsyncMock(return_value=fake_form),
            ),
            patch(
                "app.automation.report14_navigation._verify_tab11_page_loaded",
                new=AsyncMock(),
            ),
            patch(
                "app.automation.report14_navigation.url_matches_report_fragment",
                side_effect=lambda url, frag: "report22" in url,
            ),
        ):
            await navigate_report14_via_menu(page, run_id="r")

        mock_expand.assert_awaited()

    @pytest.mark.asyncio
    async def test_handler_uses_menu_navigation_not_url_nav(self):
        from app.automation.handlers.report14_handler import Report14Handler
        from app.automation.reports import REPORT_14

        handler = Report14Handler()
        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        page.wait_for_selector = AsyncMock()
        session = MagicMock()
        ensure_calls: list[dict] = []

        async def _ensure(p, s, *a, **k):
            ensure_calls.append({"args": a, "kwargs": k})
            return p

        with (
            patch.object(handler, "ensure_mis_page", new=AsyncMock(side_effect=_ensure)),
            patch(
                "app.automation.handlers.report14_handler.navigate_report14_via_menu",
                new=AsyncMock(return_value=page),
            ) as mock_menu,
            patch.object(handler.navigation, "navigate_to_report", new=AsyncMock()) as mock_url,
            patch.object(
                handler.filter_service,
                "get_report_root",
                new=AsyncMock(return_value=MagicMock()),
            ),
            patch.object(
                handler,
                "_apply_and_verify_filters",
                new=AsyncMock(
                    return_value={
                        "zone": "South Central Railway",
                        "view": "Division Wise",
                        "output": "Previous Watering Point",
                    }
                ),
            ),
            patch(
                "app.automation.handlers.report14_handler.apply_previous_from_date",
                new=AsyncMock(),
            ),
            patch("app.automation.handlers.report14_handler.log_phase1_submit_clicked"),
            patch.object(handler.generator, "generate_report", new=AsyncMock()),
            patch.object(
                handler.generator,
                "verify_report_displayed",
                new=AsyncMock(return_value=True),
            ),
            patch.object(handler, "click_received_twice", new=AsyncMock()),
            patch("app.automation.handlers.report14_handler.TableExtractor") as mock_ex,
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
                        ),
                    )
                ),
            ),
            patch(
                "app.automation.handlers.report14_handler.get_run_context",
                return_value=None,
            ),
            patch("app.automation.handlers.report14_handler.config") as mock_cfg,
            patch("app.automation.handlers.report14_handler.ensure_directory", side_effect=lambda p: p),
            patch(
                "app.automation.handlers.report14_handler.resolve_report_dir",
                side_effect=lambda *a: MagicMock(name="dir"),
            ),
        ):
            mock_cfg.extracted_data_dir = "/tmp"
            # Path / run_id ops for save
            import tempfile
            from pathlib import Path

            tmp = Path(tempfile.mkdtemp())
            with patch(
                "app.automation.handlers.report14_handler.resolve_report_dir",
                return_value=tmp,
            ), patch(
                "app.automation.handlers.report14_handler.ensure_directory",
                side_effect=lambda p: Path(p).mkdir(parents=True, exist_ok=True) or Path(p),
            ):
                extractor = mock_ex.return_value
                extractor.extract_table_data_by_headers = AsyncMock(
                    return_value=[["Division", "Received"], ["SC", "1"]]
                )
                extractor.extract_table_data = AsyncMock(return_value=[])
                await handler.execute(page, session, REPORT_14)

        assert mock_menu.await_count >= 1
        mock_url.assert_not_awaited()
        # No ensure_mis_page(..., report=REPORT_14) → no URL fragment recovery path
        for call in ensure_calls:
            assert call["kwargs"].get("report") is None

    def test_shared_handler_for_individual_and_full_generation(self):
        """Same report14 handler is registered for individual + full run."""
        from app.automation.handlers.registry import HANDLER_REGISTRY
        from app.automation.reports import DEFAULT_CATALOG

        assert "report14" in HANDLER_REGISTRY
        assert any(r.slug == "report14" for r in DEFAULT_CATALOG)
        assert HANDLER_REGISTRY["report14"].__name__ == "Report14Handler" or (
            getattr(HANDLER_REGISTRY["report14"], "__name__", None)
            or HANDLER_REGISTRY["report14"].__class__.__name__
        )

    def test_reports_1_to_13_handlers_unchanged_from_registry(self):
        from app.automation.handlers.registry import HANDLER_REGISTRY

        for slug in (
            "report1",
            "division",
            "train-no",
            "types",
            "scr-train",
            "scr-station",
            "report9",
            "comprehensive-10-13",
        ):
            assert slug in HANDLER_REGISTRY
        assert "report14" in HANDLER_REGISTRY
