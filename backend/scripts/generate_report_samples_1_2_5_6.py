"""Generate sample Excel/PDF outputs for Reports 1, 2, 5, and 6."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.automation.processing.report1_processor import Report1Processor
from app.automation.processing.report2_processor import Report2Processor
from app.automation.processing.report5_processor import Report5Processor
from app.automation.processing.report6_processor import Report6Processor

FIXTURES = ROOT / "tests" / "fixtures"
SAMPLES = ROOT / "storage" / "output" / "samples"


def _copy_outputs(result, report_key: str) -> tuple[str | None, str | None]:
    if not result.success:
        raise RuntimeError(f"{report_key} failed: {result.error}")
    excel_dest = pdf_dest = None
    if result.excel_path:
        excel_dest = SAMPLES / "excel" / report_key / Path(result.excel_path).name
        excel_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result.excel_path, excel_dest)
    if result.pdf_path:
        pdf_dest = SAMPLES / "pdf" / report_key / Path(result.pdf_path).name
        pdf_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result.pdf_path, pdf_dest)
    return (str(excel_dest) if excel_dest else None, str(pdf_dest) if pdf_dest else None)


def main() -> int:
    import app.automation.processing.report1_processor as r1_mod
    import app.automation.processing.report2_processor as r2_mod
    import app.automation.processing.report5_processor as r5_mod
    import app.automation.processing.report6_processor as r6_mod

    out_root = ROOT / "storage" / "output"
    for mod in (r1_mod, r2_mod, r5_mod, r6_mod):
        mod.config.output_excel_dir = str(out_root / "excel")
        mod.config.output_pdf_dir = str(out_root / "pdf")

    r1 = Report1Processor().process(
        source_a_path=FIXTURES / "report1" / "comprehensive_zone_raw.csv",
        source_b_path=FIXTURES / "report1" / "feedback_zone_raw.csv",
        report_slug="report1",
    )
    r2 = Report2Processor().process(
        source_a_path=FIXTURES / "report2" / "division_comprehensive_raw.csv",
        source_b_path=FIXTURES / "report2" / "division_feedback_raw.csv",
        report_slug="report2",
    )
    r5_mod.Report5Processor._find_template = lambda self: None  # type: ignore[method-assign]
    r6_mod.Report6Processor._find_template = lambda self: None  # type: ignore[method-assign]
    r5 = Report5Processor().process(
        source_a_path=FIXTURES / "report5" / "train_complaints_raw.csv",
        report_slug="report5",
    )
    r6 = Report6Processor().process(
        source_a_path=FIXTURES / "report6" / "station_complaints_raw.csv",
        report_slug="report6_station",
    )

    outputs = {
        "report1": _copy_outputs(r1, "report1"),
        "report2": _copy_outputs(r2, "report2"),
        "report5": _copy_outputs(r5, "scr-train"),
        "report6": _copy_outputs(r6, "scr-station"),
    }
    for key, (excel, pdf) in outputs.items():
        print(f"{key}: excel={excel} pdf={pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
