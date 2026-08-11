"""Unit tests for filter discovery."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.filters import FilterDiscoveryService, FilterService


@pytest.mark.asyncio
async def test_discover_fields_logs_and_saves_json(tmp_path, monkeypatch):
    monkeypatch.setattr("app.automation.filters.config.debug_screenshots_dir", str(tmp_path))

    page = MagicMock()
    frame = MagicMock()
    body = MagicMock()
    body.first.evaluate = AsyncMock(
        return_value=[
            {
                "tag": "input",
                "field_id": "fromDate",
                "field_name": "fromDate",
                "field_type": "text",
                "field_label": "From Date",
                "selector": "#fromDate",
                "current_value": "",
                "required": True,
                "options": [],
            }
        ]
    )
    frame.locator.return_value = body

    with patch.object(FilterService, "get_report_root", AsyncMock(return_value=frame)):
        fields = await FilterDiscoveryService().discover_fields(page)

    assert len(fields) == 1
    assert fields[0]["field_name"] == "fromDate"
    output = tmp_path / "report1_fields.json"
    assert output.exists()
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved[0]["selector"] == "#fromDate"
    assert saved[0]["field_label"] == "From Date"
