"""Unit tests for automation logging utilities."""

import logging

from app.automation.utils import log_automation_event


def test_log_automation_event_sanitizes_reserved_keys(caplog):
    caplog.set_level(logging.INFO)
    test_logger = logging.getLogger("test.automation.logging")

    log_automation_event(
        test_logger,
        "filter_field_discovered",
        name="fromDate",
        type="text",
        label="From Date",
        value="08/07/2026",
        id="fromDate",
    )

    assert "filter_field_discovered" in caplog.text
    assert "field_name=fromDate" in caplog.text
    assert "field_type=text" in caplog.text
    assert "field_label=From Date" in caplog.text
    assert "field_value=08/07/2026" in caplog.text
    assert "field_id=fromDate" in caplog.text


def test_log_automation_event_extra_payload_never_uses_reserved_keys(caplog):
    caplog.set_level(logging.INFO)
    test_logger = logging.getLogger("test.automation.logging.extra")

    log_automation_event(
        test_logger,
        "filter_field_discovered",
        name="dateRange",
        msg="reserved message",
        levelname="reserved level",
        filename="reserved file",
        module="reserved module",
        pathname="reserved path",
        funcName="reserved function",
        process="reserved process",
        thread="reserved thread",
    )

    record = caplog.records[-1]
    assert not hasattr(record, "field_name") or record.field_name == "dateRange"
    assert record.log_msg == "reserved message"
    assert record.log_levelname == "reserved level"
    assert record.log_filename == "reserved file"
    assert record.log_module == "reserved module"
    assert record.log_pathname == "reserved path"
    assert record.log_funcName == "reserved function"
    assert record.log_process == "reserved process"
    assert record.log_thread == "reserved thread"
