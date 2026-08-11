"""Seed original RailMadad sample workbooks and parse dataset metadata."""

from __future__ import annotations

import logging
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.datasets.service import DatasetService
from app.infrastructure.database.models import ReportDatasetModel

logger = logging.getLogger(__name__)

SAMPLE_DIR = Path(__file__).resolve().parent / "sample_workbooks"

# Representative RailMadad export columns written into sample workbooks.
RAILMADAD_SOURCE_COLUMNS = [
    "Grievance ID",
    "Zone",
    "Division",
    "Train No",
    "Train Name",
    "Station",
    "Category",
    "Sub Category",
    "Complaint Type",
    "Complaint Nature",
    "Registration Date",
    "Closed Date",
    "Current Status",
    "Feedback",
    "PNR",
    "Coach No",
    "Seat No",
    "Passenger Name",
    "Mobile Number",
    "Complaint Description",
    "Source",
    "Assigned To",
    "Priority",
    "Escalation Level",
    "Resolution Remarks",
]

REPORT_WORKBOOKS: dict[str, str] = {
    "merging": "zone_wise_original.xlsx",
    "division": "division_original.xlsx",
    "train-no": "train_original.xlsx",
    "types": "cause_wise_original.xlsx",
    "scr-train": "scr_train_original.xlsx",
    "scr-station": "scr_station_original.xlsx",
    "report1": "zone_wise_original.xlsx",
}


def _ensure_workbook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "RailMadad Data"
    sheet.append(RAILMADAD_SOURCE_COLUMNS)
    sheet.append(
        [
            "GRV-10001",
            "SCR",
            "Hyderabad",
            "12713",
            "Satavahana Express",
            "Secunderabad",
            "Catering",
            "Food Quality",
            "Complaint",
            "Service",
            "2026-07-01",
            "2026-07-02",
            "Closed",
            "Satisfied",
            "4123456789",
            "B3",
            "42",
            "Ravi Kumar",
            "9876543210",
            "Food was served cold",
            "RailMadad Portal",
            "Commercial Inspector",
            "High",
            "L1",
            "Meal replaced",
        ]
    )
    workbook.save(path)
    workbook.close()


async def seed_report_datasets(session: AsyncSession) -> None:
    existing_ids = set((await session.execute(select(ReportDatasetModel.report_id))).scalars().all())
    if existing_ids and not any(
        slug not in existing_ids for slug in REPORT_WORKBOOKS
    ):
        logger.info("Report datasets already seeded, skipping")
        return

    service = DatasetService(session)
    for report_id, filename in REPORT_WORKBOOKS.items():
        if report_id in existing_ids:
            continue
        file_path = SAMPLE_DIR / filename
        _ensure_workbook(file_path)
        await service.ingest_file(
            report_id,
            file_path=file_path,
            source_filename=filename,
            header_row=1,
        )
        logger.info("Seeded dataset metadata for report %s", report_id)
