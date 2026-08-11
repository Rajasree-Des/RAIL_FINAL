from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.seed.seed_helpers import add_setting
from app.infrastructure.seed.seed_options import (
    COMPLAINT_TYPE_OPTIONS,
    DIVISION_OPTIONS,
    OUTPUT_FORMAT_OPTIONS,
    TRAIN_TYPE_OPTIONS,
    ZONE_OPTIONS,
)


def seed_division_settings(session: AsyncSession) -> None:
    wf = "division-top-25"
    add_setting(session, wf, "reportDate", "Report Date", "date", required=True, default_value="2026-06-30", sort_order=0)
    add_setting(session, wf, "division", "Division", "dropdown", required=True, default_value="all", options=DIVISION_OPTIONS, sort_order=1)
    add_setting(session, wf, "zone", "Zone", "dropdown", required=True, default_value="all", options=ZONE_OPTIONS, sort_order=2)
    add_setting(session, wf, "outputFormat", "Output Format", "dropdown", required=True, default_value="pdf", options=OUTPUT_FORMAT_OPTIONS, sort_order=3)


def seed_train_settings(session: AsyncSession) -> None:
    wf = "train-no-top-20"
    add_setting(session, wf, "reportDate", "Date", "date", required=True, default_value="2026-06-30", sort_order=0)
    add_setting(session, wf, "trainType", "Train Type", "dropdown", required=True, default_value="all", options=TRAIN_TYPE_OPTIONS, sort_order=1)
    add_setting(session, wf, "division", "Division", "dropdown", required=True, default_value="all", options=DIVISION_OPTIONS, sort_order=2)
    add_setting(session, wf, "outputFormat", "Output Format", "dropdown", required=True, default_value="pdf", options=OUTPUT_FORMAT_OPTIONS, sort_order=3)


def seed_types_settings(session: AsyncSession) -> None:
    wf = "types-top-10"
    add_setting(session, wf, "reportDate", "Date", "date", required=True, default_value="2026-06-30", sort_order=0)
    add_setting(session, wf, "complaintType", "Complaint Type", "dropdown", required=True, default_value="all", options=COMPLAINT_TYPE_OPTIONS, sort_order=1)
    add_setting(session, wf, "division", "Division", "dropdown", required=True, default_value="all", options=DIVISION_OPTIONS, sort_order=2)
    add_setting(session, wf, "outputFormat", "Output", "dropdown", required=True, default_value="pdf", options=OUTPUT_FORMAT_OPTIONS, sort_order=3)


def seed_scr_train_settings(session: AsyncSession) -> None:
    wf = "scr-train"
    add_setting(session, wf, "reportDate", "Date", "date", required=True, default_value="2026-06-30", sort_order=0)
    add_setting(session, wf, "division", "Division", "dropdown", required=True, default_value="all", options=DIVISION_OPTIONS, sort_order=1)
    add_setting(session, wf, "outputFormat", "Output", "dropdown", required=True, default_value="pdf", options=OUTPUT_FORMAT_OPTIONS, sort_order=2)


def seed_scr_station_settings(session: AsyncSession) -> None:
    wf = "scr-station"
    add_setting(session, wf, "reportDate", "Date", "date", required=True, default_value="2026-06-30", sort_order=0)
    add_setting(session, wf, "station", "Station", "text", required=True, default_value="", sort_order=1)
    add_setting(session, wf, "division", "Division", "dropdown", required=True, default_value="all", options=DIVISION_OPTIONS, sort_order=2)
    add_setting(session, wf, "outputFormat", "Output", "dropdown", required=True, default_value="pdf", options=OUTPUT_FORMAT_OPTIONS, sort_order=3)
