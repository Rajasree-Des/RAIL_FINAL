"""Integration test: Report 14 filter apply/verify against a realistic portal-like HTML form."""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from app.automation.filters import FilterError
from app.automation.handlers.report14_handler import Report14Handler
from app.automation.report14_filters import SOURCE_PREVIOUS, SOURCE_UPCOMING
from app.automation.report14_navigation import (
    menu_text_matches_tab11,
    normalize_menu_text,
    wait_for_report14_form,
)

FIXTURE_HTML = """<!DOCTYPE html>
<html>
<head><title>RailMadad MIS</title></head>
<body>
  <div class="sidebar">
    <button id="misBtn">MIS Reports</button>
    <div id="submenu" style="display:none">
      <a href="#" id="tab10">10) Zone/Train Type wise Report</a>
      <a href="#" id="tab11">11) Train Watering
Complaints</a>
      <a href="#" id="tab12">12) Suggestion Comprehensive</a>
    </div>
  </div>
  <div class="main">
    <div>Welcome: GM_SC</div>
    <div id="formArea" style="display:none">
      <h2>Train Watering Wise Report</h2>
      <label>From Date</label><input id="fromInput" value="2026-08-04" />
      <label>To Date</label><input id="toInput" value="2026-08-04" />
      <label>Zone</label>
      <select id="complaintZoneInput">
        <option value=""></option>
        <option value="SCR">South Central Railway</option>
        <option value="NR">Northern Railway</option>
      </select>
      <label>Division</label>
      <select id="complaintDivInput">
        <option value=""></option>
        <option value="ALL">ALL</option>
        <option value="SC">SC</option>
      </select>
      <label>Sub Type</label>
      <select id="complaintSubTypeInput">
        <option value="ALL">ALL</option>
      </select>
      <label>View</label>
      <select id="viewType">
        <option value="TT">Train Type Wise</option>
        <option value="DW">Division Wise</option>
      </select>
      <label>Output</label>
      <select id="outputTypeInput">
        <option value="P">Previous Watering Point</option>
        <option value="U">Upcoming Watering Point</option>
      </select>
      <button type="button">Submit</button>
    </div>
  </div>
  <script>
    document.getElementById('misBtn').onclick = function () {
      document.getElementById('submenu').style.display = 'block';
    };
    document.getElementById('tab11').onclick = function (e) {
      e.preventDefault();
      document.getElementById('formArea').style.display = 'block';
    };
  </script>
</body>
</html>
"""


async def _launch_browser(pw):
    """Prefer system Edge when Chromium shell is not installed."""
    try:
        return await pw.chromium.launch(channel="msedge", headless=True)
    except Exception:
        return await pw.chromium.launch(headless=True)


@pytest.mark.asyncio
async def test_menu_text_wrapped_tab11():
    assert menu_text_matches_tab11("11) Train Watering\nComplaint")
    assert normalize_menu_text("11) Train Watering\nComplaint") == "11) Train Watering Complaint"


@pytest.mark.asyncio
async def test_report14_filters_applied_and_verified_on_fixture(tmp_path: Path):
    html_path = tmp_path / "r14.html"
    html_path.write_text(FIXTURE_HTML, encoding="utf-8")
    file_url = html_path.as_uri()

    async with async_playwright() as pw:
        browser = await _launch_browser(pw)
        page = await browser.new_page()
        await page.goto(file_url)

        # Expand and open tab 11 via the UI sequence
        await page.get_by_text("MIS Reports", exact=True).click()
        await page.get_by_text("11) Train Watering Complaints").click()
        form_ctx = await wait_for_report14_form(page, timeout_ms=5_000)
        assert form_ctx is not None

        handler = Report14Handler()
        root = page

        prev = await handler._apply_and_verify_filters(
            root, page, cfg=SOURCE_PREVIOUS, report_slug="report14"
        )
        assert "south central" in prev["zone"].lower()
        assert "division" in prev["view"].lower()
        assert "previous" in prev["output"].lower()

        live = await page.evaluate(
            """() => ({
              zone: document.querySelector('#complaintZoneInput').options[
                document.querySelector('#complaintZoneInput').selectedIndex].text,
              view: document.querySelector('#viewType').options[
                document.querySelector('#viewType').selectedIndex].text,
              output: document.querySelector('#outputTypeInput').options[
                document.querySelector('#outputTypeInput').selectedIndex].text,
            })"""
        )
        assert "South Central" in live["zone"]
        assert "Division" in live["view"]
        assert "Previous" in live["output"]

        up = await handler._apply_and_verify_filters(
            root, page, cfg=SOURCE_UPCOMING, report_slug="report14"
        )
        assert "upcoming" in up["output"].lower()

        # Leave zone blank and ensure verify fails
        await page.evaluate(
            "() => { document.querySelector('#complaintZoneInput').selectedIndex = 0; }"
        )
        with pytest.raises(FilterError, match="ZONE_FILTER"):
            Report14Handler._verify_core_filters(
                {"zone": "", "view": "Division Wise", "output": "Previous Watering Point"},
                cfg=SOURCE_PREVIOUS,
                report_slug="report14",
            )

        await browser.close()


@pytest.mark.asyncio
async def test_apply_rejects_default_train_type_view_without_change(tmp_path: Path):
    """If view stays Train Type Wise after apply attempt, fail-closed."""
    html = FIXTURE_HTML.replace(
        '<option value="DW">Division Wise</option>',
        "",  # remove Division Wise so apply cannot succeed
    )
    html_path = tmp_path / "r14_bad.html"
    html_path.write_text(html, encoding="utf-8")

    async with async_playwright() as pw:
        browser = await _launch_browser(pw)
        page = await browser.new_page()
        await page.goto(html_path.as_uri())
        await page.get_by_text("MIS Reports", exact=True).click()
        await page.get_by_text("11) Train Watering Complaints").click()

        handler = Report14Handler()
        with pytest.raises(FilterError, match="VIEW_FILTER|ZONE_FILTER"):
            await handler._apply_and_verify_filters(
                page, page, cfg=SOURCE_PREVIOUS, report_slug="report14"
            )
        await browser.close()
