"""Report filter discovery and application for in-process Playwright automation."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from playwright.async_api import FrameLocator, Locator, Page, TimeoutError as PlaywrightTimeoutError

from app.automation.config import config
from app.automation.report1_filters import (
    FilterFieldDefinition,
    normalize_discovered_field,
    resolve_field_value,
)
from app.automation.selectors import selectors
from app.automation.utils import ensure_directory, log_automation_event
from app.automation.wait_utils import tracked_sleep
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

ReportRoot = Page | FrameLocator

DISCOVERY_SCRIPT = """
() => {
  const results = [];
  const seen = new Set();
  const elements = document.querySelectorAll('input, select, textarea, button');
  for (const el of elements) {
    const tag = el.tagName.toLowerCase();
    const field_id = el.id || '';
    const field_name = el.name || '';
    const field_type = el.type || tag;
    const placeholder = el.placeholder || '';
    let field_label = '';
    if (field_id) {
      const labelEl = document.querySelector(`label[for="${field_id}"]`);
      if (labelEl) field_label = (labelEl.textContent || '').trim();
    }
    if (!field_label && el.closest('label')) {
      field_label = (el.closest('label').textContent || '').trim();
    }
    if (!field_label) {
      const row = el.closest('tr');
      if (row) {
        const cells = row.querySelectorAll('td, th');
        for (const cell of cells) {
          if (cell.contains(el)) continue;
          const text = (cell.textContent || '').trim();
          if (text) {
            field_label = text;
            break;
          }
        }
      }
    }
    const options = tag === 'select'
      ? Array.from(el.options).map(o => ({
          value: o.value,
          label: (o.textContent || '').trim(),
        }))
      : [];
    const selector = field_id
      ? `#${field_id}`
      : (field_name ? `[name="${field_name}"]` : tag);
    const key = `${tag}:${field_id}:${field_name}:${selector}`;
    if (seen.has(key)) continue;
    seen.add(key);
    let current_value = el.value || '';
    if (tag === 'select' && el.selectedIndex >= 0) {
      current_value = (el.options[el.selectedIndex]?.textContent || '').trim();
    }
    results.push({
      tag,
      field_id,
      field_name,
      field_type,
      placeholder,
      field_label,
      required: el.required || false,
      current_value,
      options,
      selector,
    });
  }
  return results;
}
"""


class FilterError(AppException):
    """Raised when filter discovery, application, or validation fails."""

    def __init__(self, message: str, *, code: str = "FILTER_ERROR") -> None:
        super().__init__(message=message, code=code)


class Report2FilterNotFoundError(FilterError):
    """Raised when Report 2 Source A filter field is not found after retry."""

    def __init__(self, message: str, discovered_fields: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message=message, code="REPORT2_SOURCE_A_FILTER_NOT_FOUND")
        self.discovered_fields = discovered_fields or []


async def discover_and_log_fields(
    page: Page,
    report_slug: str,
    missing_field: str | None = None,
) -> list[dict[str, Any]]:
    """Run field discovery and log all discovered fields for diagnostics.

    Called when a filter field is not found to provide debugging information.
    Saves discovered fields to a JSON file and logs each field.

    Args:
        page: The Playwright page to scan.
        report_slug: Report identifier for the output filename.
        missing_field: Optional name of the field that was not found (for logging).

    Returns:
        List of discovered field dictionaries.
    """
    from app.automation.report1_filters import normalize_discovered_field

    try:
        root = await FilterService.get_report_root(page)
        raw_fields: list[dict[str, Any]] = await root.locator("body").first.evaluate(
            DISCOVERY_SCRIPT
        )
        fields = [normalize_discovered_field(field) for field in raw_fields]
    except Exception as exc:
        logger.warning("Failed to discover fields for diagnostics: %s", exc)
        fields = []

    log_automation_event(
        logger,
        "filter_discovery_diagnostic",
        report_slug=report_slug,
        missing_field=missing_field,
        discovered_count=len(fields),
        discovered_ids=[f.get("field_id") for f in fields if f.get("field_id")],
        discovered_labels=[f.get("field_label") for f in fields if f.get("field_label")],
    )

    for field in fields:
        log_automation_event(
            logger,
            "filter_field_diagnostic",
            report_slug=report_slug,
            field_id=field.get("field_id"),
            field_name=field.get("field_name"),
            field_type=field.get("field_type"),
            field_label=field.get("field_label"),
            selector=field.get("selector"),
            current_value=field.get("current_value"),
            tag=field.get("tag"),
        )

    output_path = Path(config.debug_screenshots_dir) / f"{report_slug}_filter_diagnostic.json"
    ensure_directory(output_path.parent)
    try:
        diagnostic_data = {
            "missing_field": missing_field,
            "discovered_fields": fields,
            "field_count": len(fields),
            "select_fields": [f for f in fields if f.get("tag") == "select"],
        }
        output_path.write_text(json.dumps(diagnostic_data, indent=2), encoding="utf-8")
        log_automation_event(
            logger,
            "filter_diagnostic_saved",
            path=str(output_path),
            count=len(fields),
        )
    except Exception as exc:
        logger.warning("Failed to save filter diagnostics: %s", exc)

    return fields


async def save_filter_failure_artifacts(
    page: Page,
    report_slug: str,
    missing_field: str,
    discovered_fields: list[dict[str, Any]],
) -> str | None:
    """Save screenshot, HTML, and discovered fields on filter failure.

    Args:
        page: The Playwright page.
        report_slug: Report identifier.
        missing_field: Name of the field that was not found.
        discovered_fields: List of fields that were discovered.

    Returns:
        Path to screenshot if saved, else None.
    """
    from datetime import UTC, datetime

    dest = ensure_directory(Path(config.screenshots_dir) / "filter_failures")
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    screenshot_path: str | None = None

    try:
        url = page.url
    except Exception:
        url = None

    meta_lines = [
        f"report_slug={report_slug}",
        f"missing_field={missing_field}",
        f"url={url}",
        f"timestamp={timestamp}",
        f"discovered_field_count={len(discovered_fields)}",
        f"discovered_ids={[f.get('field_id') for f in discovered_fields if f.get('field_id')]}",
    ]
    meta_path = dest / f"filter_failure_{timestamp}_{report_slug}.txt"
    try:
        meta_path.write_text("\n".join(meta_lines) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write filter failure metadata: %s", exc)

    fields_path = dest / f"filter_failure_{timestamp}_{report_slug}_fields.json"
    try:
        fields_path.write_text(json.dumps(discovered_fields, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write discovered fields: %s", exc)

    try:
        html = await page.content()
        html_path = dest / f"filter_failure_{timestamp}_{report_slug}.html"
        html_path.write_text(html, encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write filter failure HTML: %s", exc)

    try:
        screenshot_file = dest / f"filter_failure_{timestamp}_{report_slug}.png"
        await page.screenshot(path=str(screenshot_file), full_page=True)
        screenshot_path = str(screenshot_file)
    except Exception as exc:
        logger.warning("Could not capture filter failure screenshot: %s", exc)

    log_automation_event(
        logger,
        "filter_failure_artifacts_saved",
        report_slug=report_slug,
        missing_field=missing_field,
        url=url,
        screenshot_path=screenshot_path,
        meta_path=str(meta_path),
        fields_path=str(fields_path),
    )

    return screenshot_path


class FilterDiscoveryService:
    """Discovers form fields inside the Report 1 page or iframe."""

    async def discover_fields(self, page: Page) -> list[dict[str, Any]]:
        """Scan the report surface and persist discovered field metadata."""
        root = await FilterService.get_report_root(page)
        raw_fields: list[dict[str, Any]] = await root.locator("body").first.evaluate(
            DISCOVERY_SCRIPT
        )
        fields = [normalize_discovered_field(field) for field in raw_fields]

        for field in fields:
            log_automation_event(
                logger,
                "filter_field_discovered",
                field_name=field.get("field_name") or field.get("field_id") or field.get("tag"),
                field_id=field.get("field_id"),
                field_type=field.get("field_type"),
                selector=field.get("selector"),
                field_label=field.get("field_label"),
                field_value=field.get("current_value"),
            )

        return fields


class FilterService:
    """Applies configured filters to the Report 1 form."""

    @staticmethod
    async def get_report_root(page: Page) -> ReportRoot:
        """Return the page or iframe containing the report filter form."""
        deadline = 20_000
        try:
            await page.wait_for_selector(
                "select, input, textarea, iframe",
                timeout=deadline,
            )
        except PlaywrightTimeoutError:
            logger.warning("Timed out waiting for report form controls")

        # Portal report forms often load asynchronously inside an iframe
        for _ in range(10):
            iframe_count = await page.locator("iframe").count()
            for index in range(iframe_count):
                frame_loc = page.frame_locator("iframe").nth(index)
                try:
                    count = await frame_loc.locator("input, select, textarea").count()
                except Exception:
                    count = 0
                if count > 0:
                    log_automation_event(
                        logger,
                        "report_context_resolved",
                        location="iframe",
                        frame_index=index,
                    )
                    return frame_loc

            for frame_selector in selectors.report1_frame.split(","):
                frame_selector = frame_selector.strip()
                if not frame_selector:
                    continue
                frame_loc = page.frame_locator(frame_selector).first
                try:
                    count = await frame_loc.locator("input, select, textarea").count()
                except Exception:
                    count = 0
                if count > 0:
                    log_automation_event(
                        logger,
                        "report_context_resolved",
                        location="iframe",
                        frame_selector=frame_selector,
                    )
                    return frame_loc

            if await page.locator("select, input, textarea").count() > 0:
                log_automation_event(logger, "report_context_resolved", location="main_page")
                return page

            await tracked_sleep(0.15, reason="report_root_iframe_poll")

        raise FilterError("Report form not found on the page (no iframe or main-page controls)")

    @staticmethod
    async def get_report_frame(page: Page) -> ReportRoot:
        """Backward-compatible alias for get_report_root."""
        return await FilterService.get_report_root(page)

    async def apply_filters(
        self,
        root: ReportRoot,
        fields: list[FilterFieldDefinition],
        page: Page | None = None,
    ) -> dict[str, str]:
        """Populate all configured filters and return applied name/value pairs."""
        applied: dict[str, str] = {}
        date_format = config.date_format

        for field in fields:
            locator = await self._resolve_field_locator(root, field)
            if await locator.count() == 0:
                if field.required:
                    raise FilterError(
                        f"Required filter field not found: {field.name} ({field.selector})"
                    )
                logger.warning("Optional filter field not found: %s", field.name)
                continue

            value = resolve_field_value(field, date_format=date_format)
            applied_value, changed = await self._apply_field(locator, field, value)
            applied[field.name] = applied_value
            if changed:
                log_automation_event(
                    logger,
                    "filter_field_set",
                    field_name=field.name,
                    field_value=applied_value,
                    field_label=field.label or field.name,
                )
            else:
                log_automation_event(
                    logger,
                    "filter_field_unchanged",
                    field_name=field.name,
                    field_value=applied_value,
                )
            # Cascading portal selects need a short settle only when value changed.
            cascading = field.name.lower() in {
                "zone",
                "division",
                "type",
                "sub_type",
                "department",
                "mode",
                "daterange",
                "view",
            }
            if cascading and changed:
                delay_ms = min(config.filter_interaction_delay_ms, 80)
                if delay_ms > 0:
                    await tracked_sleep(delay_ms / 1000, reason="cascading_filter_settle")
                if field.field_type == "select" and page is not None:
                    await self._wait_for_dependent_controls(page)

        return applied

    @staticmethod
    async def _wait_for_dependent_controls(page: Page) -> None:
        try:
            await page.locator("select, input").first.wait_for(
                state="attached", timeout=1_500
            )
        except PlaywrightTimeoutError:
            logger.debug("dependent controls wait skipped after filter change")

    async def _resolve_field_locator(
        self,
        root: ReportRoot,
        field: FilterFieldDefinition,
    ) -> Locator:
        locator = root.locator(field.selector).first
        if await locator.count() > 0:
            return locator

        if field.label:
            label_locator = root.locator(
                f"tr:has(td:text-is('{field.label}')) select, "
                f"tr:has(td:text-is('{field.label}')) input, "
                f"tr:has(th:text-is('{field.label}')) select, "
                f"tr:has(th:text-is('{field.label}')) input, "
                f"td:text-is('{field.label}') + td select, "
                f"td:text-is('{field.label}') + td input, "
                f"label:text-is('{field.label}') + select, "
                f"label:text-is('{field.label}') + input, "
                f"tr:has(td:has-text('{field.label}')) select, "
                f"tr:has(th:has-text('{field.label}')) select, "
                f"td:has-text('{field.label}') + td select, "
                f"label:has-text('{field.label}') + select"
            ).first
            if await label_locator.count() > 0:
                return label_locator

        return locator

    async def _apply_field(
        self,
        locator: Locator,
        field: FilterFieldDefinition,
        value: str,
    ) -> tuple[str, bool]:
        if field.field_type == "select":
            applied, changed = await self._apply_select(locator, value)
            return applied, changed
        if field.field_type == "checkbox":
            await self._apply_checkbox(locator, value)
            return value, True
        if field.field_type == "radio":
            await self._apply_radio(locator, value)
            return value, True
        await self._apply_text_or_date(locator, value)
        return value, True

    async def _apply_text_or_date(self, locator: Locator, value: str) -> None:
        if not await locator.is_visible():
            await locator.evaluate(
                """(el, value) => {
                    el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                value,
            )
            return
        try:
            await locator.fill(value)
        except Exception:
            await locator.click()
            await locator.fill(value)
            await locator.press("Enter")

    async def _apply_select(self, locator: Locator, value: str) -> tuple[str, bool]:
        current = await locator.evaluate(
            "el => (el.options[el.selectedIndex]?.text ?? el.value ?? '').trim()"
        )
        current_norm = str(current or "").strip().lower()
        value_norm = value.strip().lower()
        if current_norm and (
            current_norm == value_norm
            or value_norm in current_norm
            or current_norm in value_norm
        ):
            return str(current), False

        candidates = [value]
        normalized = value.lower().strip()
        if normalized in {"previous day", "prev_day", "previous_day", "today_range", "previous_day_range"}:
            candidates.extend(
                [
                    "Previous Day",
                    "PREV_DAY",
                    "PREVIOUS DAY",
                    "PreviousDay",
                ]
            )
        elif normalized == "today":
            candidates.extend(["Today", "Current Day", "CURRENT DAY", "TODAY"])
        elif normalized in {"carriage & wagon", "carriage and wagon", "c&w"}:
            candidates.extend(
                ["Carriage & Wagon", "Carriage And Wagon", "C&W", "CARRIAGE & WAGON", "Carriage&Wagon"]
            )
        elif normalized in {"security-train", "security - train", "security train", "security- train"}:
            candidates.extend(
                [
                    "Security-Train",
                    "Security - Train",
                    "Security- Train",
                    "SECURITY-TRAIN",
                    "Security Train",
                ]
            )
        elif normalized in {"punctuality-train", "punctuality - train", "punctuality train", "punctuality- train", "punctuality"}:
            candidates.extend(
                [
                    "Punctuality-Train",
                    "Punctuality - Train",
                    "Punctuality- Train",
                    "PUNCTUALITY-TRAIN",
                    "Punctuality Train",
                    "Punctuality",
                ]
            )
        elif "electrical" in normalized and ("train" in normalized or "equipment" in normalized):
            candidates.extend(
                [
                    "Electrical Equipment-Train",
                    "Electrical Equipment - Train",
                    "Electrical Equipment- Train",
                    "ELECTRICAL EQUIPMENT-TRAIN",
                    "Electrical Equipment Train",
                    "Electrical Equip-Train",
                    "Electrical Equipment",
                ]
            )
        elif normalized == "all":
            candidates.extend(["ALL", "All", "all", "--All--", "-- All --"])
        elif normalized == "train":
            candidates.extend(["Train", "TRAIN", "train"])
        elif normalized in {"south central railway", "scr"}:
            candidates.extend(
                ["South Central Railway", "SCR", "SOUTH CENTRAL RAILWAY", "South-Central Railway"]
            )
        elif normalized in {"division wise", "divisionwise"}:
            candidates.extend(["Division Wise", "DivisionWise", "DIVISION WISE", "Division-Wise"])
        for candidate in candidates:
            try:
                await locator.select_option(label=candidate)
                return candidate, True
            except Exception:
                try:
                    await locator.select_option(value=candidate)
                    return candidate, True
                except Exception:
                    continue

        selected = await locator.evaluate(
            "el => el.options[el.selectedIndex]?.text ?? ''"
        )
        if selected:
            return str(selected), True

        available_options = await locator.evaluate(
            "el => Array.from(el.options).map(o => ({value: o.value, label: (o.text || '').trim()}))"
        )
        log_automation_event(
            logger,
            "filter_select_failed",
            requested_value=value,
            candidates_tried=candidates,
            available_options=available_options,
        )
        raise FilterError(
            f"Could not select option '{value}' for dropdown. "
            f"Tried: {candidates}. Available: {available_options}"
        )

    async def _apply_checkbox(self, locator: Locator, value: str) -> None:
        should_check = value.lower() in {"true", "1", "yes", "on", "checked"}
        if should_check and not await locator.is_checked():
            await locator.check()

    async def _apply_radio(self, locator: Locator, value: str) -> None:
        target = locator
        if await locator.count() > 1:
            target = locator.filter(has_text=value).first
            if await target.count() == 0:
                target = locator.locator(f"[value='{value}']").first
        if await target.count() > 0 and not await target.is_checked():
            await target.check()

    async def validate_mandatory(
        self,
        root: ReportRoot,
        fields: list[FilterFieldDefinition],
        applied: dict[str, str],
    ) -> None:
        """Ensure every required filter has a non-empty value."""
        missing: list[str] = []
        for field in fields:
            if not field.required:
                continue
            locator = await self._resolve_field_locator(root, field)
            if await locator.count() == 0:
                missing.append(f"{field.name} (not found)")
                continue
            current = applied.get(field.name, "")
            if not str(current).strip():
                current = await self._read_field_value(locator, field.field_type)
            if not str(current).strip():
                missing.append(field.name)

        if missing:
            raise FilterError(f"Mandatory filters missing or empty: {', '.join(missing)}")

        log_automation_event(logger, "filters_validated", count=len(applied))

    @staticmethod
    async def _read_field_value(locator: Locator, field_type: str) -> str:
        if field_type == "select":
            return str(
                await locator.evaluate("el => el.options[el.selectedIndex]?.text ?? ''")
            )
        try:
            return await locator.input_value()
        except Exception:
            return ""
