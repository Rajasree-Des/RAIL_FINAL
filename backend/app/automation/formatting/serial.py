"""Final S.No. regeneration helpers (shared across reports)."""

from __future__ import annotations


def is_serial_header(header: str) -> bool:
    """Return True for serial-number column headers (S.No., SNo, etc.)."""
    normalized = header.strip().lower().replace(" ", "").replace("_", "")
    return normalized in {"s.no.", "s.no", "sno", "sl.no.", "sl.no", "slno", "serialno"}


def apply_serial_number(
    headers: list[str],
    values: list[str],
    serial: int | None,
) -> list[str]:
    """
    Overwrite S.No. columns in a row.

    Pass serial=None for totals/footer rows so they do not receive a normal 1..N value.
    """
    out: list[str] = []
    for idx, header in enumerate(headers):
        current = values[idx] if idx < len(values) else ""
        if is_serial_header(header):
            out.append("" if serial is None else str(serial))
        else:
            out.append(current)
    return out


def renumber_data_rows(
    headers: list[str],
    rows: list[list[str]],
    *,
    skip_total: bool = True,
) -> list[list[str]]:
    """
    Regenerate S.No. as 1..N for data rows after final order is fixed.

    When skip_total is True, the last row is treated as a totals row if any
    Organisation/Division cell contains 'total'.
    """
    if not rows:
        return rows

    total_idx: int | None = None
    if skip_total:
        last = rows[-1]
        joined = " ".join(str(v) for v in last).lower()
        if "total" in joined:
            total_idx = len(rows) - 1

    output: list[list[str]] = []
    serial = 1
    for idx, row in enumerate(rows):
        if total_idx is not None and idx == total_idx:
            output.append(apply_serial_number(headers, row, None))
        else:
            output.append(apply_serial_number(headers, row, serial))
            serial += 1
    return output
