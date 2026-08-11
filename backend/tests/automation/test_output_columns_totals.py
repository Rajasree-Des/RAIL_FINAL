"""Unit tests for Report 1/2 totals row computation."""

from __future__ import annotations

from app.automation.processing.output_columns import (
    AGGREGATE_HEADERS,
    SOURCE_B_DATA_COLUMNS,
    apply_report1_totals_to_report2_row,
    build_merged_total_row,
    fill_report1_avg_disposal_time_total,
    report2_columns_to_copy_from_report1,
    validate_report2_common_totals_match_report1,
    _parse_time_to_minutes,
    _weighted_time_average_with_stats,
)

SOURCE_A_HEADERS = [
    "S.No.",
    "Organisation",
    "Opening Balance",
    "Received",
    "% Share",
    "Closed",
    "Closing Balance",
    "% Disposal",
    "Avg. Disposal Time",
    "Avg. Rating",
    "Avg. Pendency Time",
    "Forwarded",
    "Avg. FRT",
]


def _row(*values: str) -> list[str]:
    return list(values)


def test_build_merged_total_row_closing_balance_backfill():
    data_rows = [
        _row("1", "A", "10", "100", "5", "90", "20", "90.00", "", "", "", "50", ""),
        _row("2", "B", "5", "200", "10", "180", "25", "90.00", "", "", "", "60", ""),
    ]
    total_a = {
        "S.No.": "20",
        "Organisation": "Total",
        "Opening Balance": "",
        "Received": "300",
        "% Share": "",
        "Closed": "270",
        "Closing Balance": "",
        "% Disposal": "",
        "Avg. Disposal Time": "",
        "Avg. Rating": "",
        "Avg. Pendency Time": "",
        "Forwarded": "",
        "Avg. FRT": "",
    }
    merged = build_merged_total_row(
        merged_headers=SOURCE_A_HEADERS + [""] + ["Organisation"] + SOURCE_B_DATA_COLUMNS,
        data_rows=data_rows,
        source_a_headers=SOURCE_A_HEADERS,
        source_b_headers=["Organisation"] + SOURCE_B_DATA_COLUMNS,
        total_a=total_a,
        total_b=None,
        source_b_columns=SOURCE_B_DATA_COLUMNS,
        org_label_a="Total",
    )
    closing_idx = SOURCE_A_HEADERS.index("Closing Balance")
    assert merged[closing_idx] == "30"


def test_build_merged_total_row_pct_disposal_uses_opening_plus_received():
    data_rows = [
        _row("1", "A", "10", "100", "10", "80", "30", "", "", "", "", "0", ""),
    ]
    total_a = {
        "S.No.": "",
        "Organisation": "Total",
        "Opening Balance": "15",
        "Received": "9320",
        "% Share": "",
        "Closed": "8660",
        "Closing Balance": "",
        "% Disposal": "",
        "Avg. Disposal Time": "",
        "Avg. Rating": "",
        "Avg. Pendency Time": "",
        "Forwarded": "",
        "Avg. FRT": "",
    }
    merged = build_merged_total_row(
        merged_headers=SOURCE_A_HEADERS + [""] + ["Organisation"] + SOURCE_B_DATA_COLUMNS,
        data_rows=data_rows,
        source_a_headers=SOURCE_A_HEADERS,
        source_b_headers=["Organisation"] + SOURCE_B_DATA_COLUMNS,
        total_a=total_a,
        total_b=None,
        source_b_columns=SOURCE_B_DATA_COLUMNS,
        org_label_a="Total / All Divisions",
    )
    disposal_idx = SOURCE_A_HEADERS.index("% Disposal")
    assert merged[disposal_idx] == "92.77"


def test_aggregate_columns_not_summed_naively():
    data_rows = [
        _row("1", "A", "0", "100", "10", "80", "20", "80.00", "0:30", "", "", "0", "0:10"),
        _row("2", "B", "0", "200", "20", "160", "40", "80.00", "0:45", "", "", "0", "0:15"),
    ]
    total_a = {
        "S.No.": "",
        "Organisation": "Total",
        "Opening Balance": "",
        "Received": "300",
        "% Share": "",
        "Closed": "240",
        "Closing Balance": "60",
        "% Disposal": "80.00",
        "Avg. Disposal Time": "",
        "Avg. Rating": "",
        "Avg. Pendency Time": "",
        "Forwarded": "",
        "Avg. FRT": "",
    }
    merged = build_merged_total_row(
        merged_headers=SOURCE_A_HEADERS + [""] + ["Organisation"] + SOURCE_B_DATA_COLUMNS,
        data_rows=data_rows,
        source_a_headers=SOURCE_A_HEADERS,
        source_b_headers=["Organisation"] + SOURCE_B_DATA_COLUMNS,
        total_a=total_a,
        total_b=None,
        source_b_columns=SOURCE_B_DATA_COLUMNS,
        org_label_a="Total",
    )
    avg_idx = SOURCE_A_HEADERS.index("Avg. Disposal Time")
    assert merged[avg_idx] == ""
    assert "Avg. Disposal Time" in AGGREGATE_HEADERS


def test_report1_portal_avg_disposal_time_preferred():
    data_rows = [
        _row("1", "A", "0", "100", "10", "80", "20", "80.00", "0:30", "", "", "0", "0:10"),
        _row("2", "B", "0", "200", "20", "160", "40", "80.00", "0:45", "", "", "0", "0:15"),
    ]
    total_a = {
        "S.No.": "",
        "Organisation": "Total",
        "Opening Balance": "",
        "Received": "300",
        "% Share": "",
        "Closed": "240",
        "Closing Balance": "60",
        "% Disposal": "80.00",
        "Avg. Disposal Time": "0:35",
        "Avg. Rating": "",
        "Avg. Pendency Time": "",
        "Forwarded": "",
        "Avg. FRT": "",
    }
    merged = build_merged_total_row(
        merged_headers=SOURCE_A_HEADERS + [""] + ["Organisation"] + SOURCE_B_DATA_COLUMNS,
        data_rows=data_rows,
        source_a_headers=SOURCE_A_HEADERS,
        source_b_headers=["Organisation"] + SOURCE_B_DATA_COLUMNS,
        total_a=total_a,
        total_b=None,
        source_b_columns=SOURCE_B_DATA_COLUMNS,
        org_label_a="Total",
    )
    fill_report1_avg_disposal_time_total(
        merged,
        source_a_headers=SOURCE_A_HEADERS,
        data_rows=data_rows,
        total_a=total_a,
    )
    avg_idx = SOURCE_A_HEADERS.index("Avg. Disposal Time")
    assert merged[avg_idx] == "0:35"


def test_report1_weighted_avg_disposal_time_fallback():
    data_rows = [
        _row("1", "A", "0", "100", "10", "80", "20", "80.00", "0:30", "", "", "0", "0:10"),
        _row("2", "B", "0", "200", "20", "160", "40", "80.00", "0:45", "", "", "0", "0:15"),
    ]
    total_a = {
        "S.No.": "",
        "Organisation": "Total",
        "Opening Balance": "",
        "Received": "300",
        "% Share": "",
        "Closed": "240",
        "Closing Balance": "60",
        "% Disposal": "80.00",
        "Avg. Disposal Time": "",
        "Avg. Rating": "",
        "Avg. Pendency Time": "",
        "Forwarded": "",
        "Avg. FRT": "",
    }
    merged = build_merged_total_row(
        merged_headers=SOURCE_A_HEADERS + [""] + ["Organisation"] + SOURCE_B_DATA_COLUMNS,
        data_rows=data_rows,
        source_a_headers=SOURCE_A_HEADERS,
        source_b_headers=["Organisation"] + SOURCE_B_DATA_COLUMNS,
        total_a=total_a,
        total_b=None,
        source_b_columns=SOURCE_B_DATA_COLUMNS,
        org_label_a="Total",
    )
    result = fill_report1_avg_disposal_time_total(
        merged,
        source_a_headers=SOURCE_A_HEADERS,
        data_rows=data_rows,
        total_a=total_a,
    )
    avg_idx = SOURCE_A_HEADERS.index("Avg. Disposal Time")
    # (30*80 + 45*160) / 240 = 9600/240 = 40 minutes
    assert merged[avg_idx] == "0:40"
    assert result.source == "weighted_fallback"
    assert result.valid_rows_used == 2
    assert result.total_closed_weight == 240
    assert result.calculated_minutes == 40.0


def test_report1_weighted_avg_ignores_invalid_and_zero_closed():
    data_rows = [
        _row("1", "A", "0", "100", "10", "80", "20", "80.00", "0:30", "", "", "0", "0:10"),
        _row("2", "B", "0", "200", "20", "0", "40", "80.00", "0:45", "", "", "0", "0:15"),
        _row("3", "C", "0", "50", "5", "40", "10", "80.00", "", "", "", "0", "0:05"),
        _row("4", "D", "0", "50", "5", "20", "30", "80.00", "bad", "", "", "0", "0:05"),
        _row("", "Total", "", "400", "", "140", "", "", "", "", "", "", ""),
    ]
    merged = build_merged_total_row(
        merged_headers=SOURCE_A_HEADERS + [""] + ["Organisation"] + SOURCE_B_DATA_COLUMNS,
        data_rows=data_rows[:4],
        source_a_headers=SOURCE_A_HEADERS,
        source_b_headers=["Organisation"] + SOURCE_B_DATA_COLUMNS,
        total_a=None,
        total_b=None,
        source_b_columns=SOURCE_B_DATA_COLUMNS,
        org_label_a="Total",
    )
    fill_report1_avg_disposal_time_total(
        merged,
        source_a_headers=SOURCE_A_HEADERS,
        data_rows=data_rows,
        total_a=None,
    )
    avg_idx = SOURCE_A_HEADERS.index("Avg. Disposal Time")
    assert merged[avg_idx] == "0:30"


def test_report1_hmm_formatting():
    assert _parse_time_to_minutes("0:39") == 39
    assert _parse_time_to_minutes("1:06") == 66
    assert _parse_time_to_minutes("  1:06  ") == 66
    assert _parse_time_to_minutes("") is None
    assert _parse_time_to_minutes("-") is None
    assert _parse_time_to_minutes("bad") is None

    stats = _weighted_time_average_with_stats(
        [_row("1", "A", "0", "0", "0", "10", "0", "0", "1:06", "", "", "0", "")],
        SOURCE_A_HEADERS.index("Avg. Disposal Time"),
        SOURCE_A_HEADERS.index("Closed"),
    )
    assert stats.formatted_result == "1:06"


def test_report1_avg_disposal_survives_column_projection():
    from app.automation.processing.column_config import project_for_output

    data_rows = [
        _row("1", "A", "0", "100", "10", "80", "20", "80.00", "0:30", "", "", "0", "0:10"),
    ]
    merged_headers = SOURCE_A_HEADERS + [""] + ["Organisation"] + SOURCE_B_DATA_COLUMNS
    merged_row = _row(
        "1", "A", "0", "100", "10", "80", "20", "80.00", "0:30", "", "", "0", "0:10",
        "1", "A", "50", "50.00", "10", "30", "10", "20.00",
    )
    total_row = build_merged_total_row(
        merged_headers=merged_headers,
        data_rows=[merged_row],
        source_a_headers=SOURCE_A_HEADERS,
        source_b_headers=["Organisation"] + SOURCE_B_DATA_COLUMNS,
        total_a=None,
        total_b=None,
        source_b_columns=SOURCE_B_DATA_COLUMNS,
        org_label_a="Total",
    )
    fill_report1_avg_disposal_time_total(
        total_row,
        source_a_headers=SOURCE_A_HEADERS,
        data_rows=[merged_row],
        total_a=None,
    )
    merged_rows = [merged_row, total_row]
    output_headers, output_rows, _, _, _ = project_for_output(
        "report1",
        full_headers=merged_headers,
        rows=merged_rows,
    )
    avg_idx = output_headers.index("Avg. Disposal Time")
    assert output_rows[-1][avg_idx] == "0:30"


def test_apply_report1_totals_only_copies_shared_column_names():
    headers = [
        "Organisation",
        "Received",
        "% Share",
        "Closed",
        "Opening Balance",
        "Feedback Received",
    ]
    calculated = ["Total", "100", "50.00", "80", "999", "40"]
    report1_totals = {
        "Received": "9321",
        "% Share": "100.00",
        "Closed": "8660",
        "Opening Balance": "0",
        "Feedback Received": "1800",
    }
    result = apply_report1_totals_to_report2_row(calculated, headers, report1_totals)
    assert result[headers.index("Received")] == "9321"
    assert result[headers.index("% Share")] == "100.00"
    assert result[headers.index("Closed")] == "8660"
    assert result[headers.index("Feedback Received")] == "1800"
    assert result[headers.index("Opening Balance")] == "999"


def test_report2_columns_to_copy_is_name_based_not_positional():
    report2_headers = ["Division", "Closed", "Received"]
    report1_totals = {"Received": "1", "Closed": "2", "Extra": "9"}
    copied = report2_columns_to_copy_from_report1(report2_headers, report1_totals)
    assert copied == ["Closed", "Received"]


def test_validate_report2_common_totals_match_report1_raises_on_mismatch():
    headers = ["Organisation", "Received"]
    row = ["Total", "100"]
    report1 = {"Received": "9321"}
    try:
        validate_report2_common_totals_match_report1(row, headers, report1)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Received" in str(exc)
