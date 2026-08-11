"""Build merged preview tables for Report 1/2 without CDP or file output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.automation.formatting.scr import mode_matches
from app.automation.processing.column_config import project_scr_for_output, project_selected_columns
from app.automation.processing.report1_processor import Report1Processor
from app.automation.processing.report2_processor import Report2Processor
from app.automation.processing.report3_processor import Report3Processor
from app.automation.processing.report4_processor import Report4Processor
from app.automation.processing.report5_processor import Report5Processor
from app.automation.processing.report6_processor import Report6Processor
from app.automation.processing.scr_output_columns import SCR_NAMESPACED_SLUGS
from app.automation.processing.topn_output_columns import TOPN_REPORT_SLUGS
from app.automation.report_keys import canonicalize_report_key
from app.automation.scr_field_map import canonicalize_scr_rows
from app.infrastructure.database.models import ReportDatasetModel
from app.infrastructure.database.session import SessionLocal

FEEDBACK_DATASET_ID = "report1_feedback"
DIVISION_FEEDBACK_DATASET_ID = "division_feedback"

NO_DATA_MESSAGE = "No generated report data is available for preview."


async def resolve_source_paths(report_slug: str) -> tuple[Path, Path] | None:
    """Load latest ingested Source A and Source B CSV paths for R1/R2."""
    slug = canonicalize_report_key(report_slug)
    if slug not in {"report1", "division"}:
        return None

    feedback_id = FEEDBACK_DATASET_ID if slug == "report1" else DIVISION_FEEDBACK_DATASET_ID

    async with SessionLocal() as session:
        source_a_result = await session.execute(
            select(ReportDatasetModel).where(ReportDatasetModel.report_id == slug).limit(1)
        )
        source_a_model = source_a_result.scalar_one_or_none()
        feedback_result = await session.execute(
            select(ReportDatasetModel)
            .where(ReportDatasetModel.report_id == feedback_id)
            .limit(1)
        )
        feedback_model = feedback_result.scalar_one_or_none()

    if (
        source_a_model is None
        or not source_a_model.source_file_path
        or feedback_model is None
        or not feedback_model.source_file_path
    ):
        return None

    source_a = Path(source_a_model.source_file_path)
    source_b = Path(feedback_model.source_file_path)
    if not source_a.is_file() or not source_b.is_file():
        return None
    if source_a.suffix.lower() == ".pdf" or source_b.suffix.lower() == ".pdf":
        return None
    return source_a, source_b


def build_merged_preview_table(
    report_slug: str,
    source_a_path: Path,
    source_b_path: Path,
) -> tuple[list[str], list[list[str]]] | None:
    """Run merge + totals only; return None when merge cannot be built."""
    slug = canonicalize_report_key(report_slug)
    if slug == "report1":
        processor = Report1Processor()
        source_a_rows, source_a_headers = processor._read_csv(source_a_path)
        source_b_rows, source_b_headers = processor._read_csv(source_b_path)
        return processor.build_merged_table(
            source_a_rows,
            source_a_headers,
            source_b_rows,
            source_b_headers,
        )[:2]

    if slug == "division":
        processor = Report2Processor()
        source_a_rows, source_a_headers = processor._read_csv(source_a_path)
        source_b_rows, source_b_headers = processor._read_csv(source_b_path)
        return processor.build_merged_table(
            source_a_rows,
            source_a_headers,
            source_b_rows,
            source_b_headers,
        )[:2]

    return None


@dataclass(frozen=True)
class ScrDatasetRef:
    dataset_id: str
    path: Path
    row_count: int


async def resolve_scr_dataset(report_slug: str) -> ScrDatasetRef | None:
    """Load ingested SCR dataset metadata and path (same lookup as preview)."""
    slug = canonicalize_report_key(report_slug)
    if slug not in SCR_NAMESPACED_SLUGS:
        return None

    async with SessionLocal() as session:
        result = await session.execute(
            select(ReportDatasetModel).where(ReportDatasetModel.report_id == slug).limit(1)
        )
        model = result.scalar_one_or_none()

    if model is None or not model.source_file_path:
        return None
    path = Path(model.source_file_path)
    if not path.is_file() or path.suffix.lower() == ".pdf":
        return None
    return ScrDatasetRef(
        dataset_id=model.id,
        path=path,
        row_count=int(model.row_count or 0),
    )


async def resolve_scr_source_path(report_slug: str) -> Path | None:
    ref = await resolve_scr_dataset(report_slug)
    return ref.path if ref else None


def _read_scr_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    processor = Report5Processor()
    rows, headers = processor._read_csv(path)
    rows = canonicalize_scr_rows(rows)
    if rows:
        headers = sorted({k for row in rows for k in row})
    return rows, headers


def build_scr_preview_rows(
    report_slug: str,
    source_path: Path,
    *,
    selected_column_ids: list[str],
    column_order: list[str],
) -> dict[str, object]:
    slug = canonicalize_report_key(report_slug)
    order = column_order or selected_column_ids
    rows, _headers = _read_scr_csv(source_path)

    expected_mode = "Train" if slug in {"scr-train", "report5"} else "Station"
    filtered = [
        row
        for row in rows
        if mode_matches(
            expected_mode,
            row.get("complaintMode", "") or row.get("mode", "") or row.get("Mode", ""),
        )
    ]

    output_headers, output_rows, visible_columns, resolved_keys, _config_source = (
        project_scr_for_output(
            slug,
            filtered,
            selected_keys=order,
            config_source="manual_snapshot",
        )
    )

    preview_rows: list[dict[str, str]] = []
    for row in output_rows[:10]:
        preview_rows.append(
            {header: row[idx] if idx < len(row) else "" for idx, header in enumerate(output_headers)}
        )

    return {
        "available": True,
        "report_slug": slug,
        "visible_columns": visible_columns,
        "preview_rows": preview_rows,
        "selected_count": len(resolved_keys),
        "selected_column_ids": list(resolved_keys),
        "column_order": list(order),
        "preview_version": len(resolved_keys),
    }


async def resolve_topn_dataset(report_slug: str) -> Path | None:
    """Load ingested Top-N dataset path for Report 3 or 4."""
    slug = canonicalize_report_key(report_slug)
    if slug not in TOPN_REPORT_SLUGS:
        return None

    async with SessionLocal() as session:
        result = await session.execute(
            select(ReportDatasetModel).where(ReportDatasetModel.report_id == slug).limit(1)
        )
        model = result.scalar_one_or_none()

    if model is None or not model.source_file_path:
        return None
    path = Path(model.source_file_path)
    if not path.is_file() or path.suffix.lower() == ".pdf":
        return None
    return path


def build_train_no_preview_rows(
    source_path: Path,
    *,
    selected_column_ids: list[str],
    column_order: list[str],
) -> dict[str, object]:
    order = column_order or selected_column_ids
    selection = {
        "selected_column_ids": order,
        "column_order": order,
        "configuration_source": "manual_snapshot",
    }
    output_headers, output_rows, visible_columns, resolved_keys, _config_source = (
        Report3Processor.build_projected_table(
            source_path,
            report_slug="train-no",
            column_selection=selection,
        )
    )
    preview_rows: list[dict[str, str]] = []
    for row in output_rows[:10]:
        preview_rows.append(
            {header: row[idx] if idx < len(row) else "" for idx, header in enumerate(output_headers)}
        )
    return {
        "available": True,
        "report_slug": "train-no",
        "visible_columns": visible_columns,
        "preview_rows": preview_rows,
        "selected_count": len(resolved_keys),
        "selected_column_ids": list(resolved_keys),
        "column_order": list(order),
        "preview_version": len(resolved_keys),
    }


def build_types_preview_rows(
    index_path: Path,
    *,
    selected_column_ids: list[str],
    column_order: list[str],
) -> dict[str, object]:
    order = column_order or selected_column_ids
    selection = {
        "selected_column_ids": order,
        "column_order": order,
        "configuration_source": "manual_snapshot",
    }
    sections, output_headers, resolved_keys, _config_source = Report4Processor.build_projected_sections(
        index_path,
        report_slug="types",
        column_selection=selection,
    )
    section_payload: list[dict[str, object]] = []
    for section in sections:
        rows: list[dict[str, str]] = []
        for row in section.rows[:10]:
            rows.append(
                {
                    header: row[idx] if idx < len(row) else ""
                    for idx, header in enumerate(section.headers)
                }
            )
        section_payload.append(
            {
                "title": section.type_config.section_title,
                "headers": section.headers,
                "rows": rows,
                "empty": len(section.rows) == 0,
            }
        )
    return {
        "available": True,
        "report_slug": "types",
        "visible_columns": output_headers,
        "preview_rows": [],
        "sections": section_payload,
        "selected_count": len(resolved_keys),
        "selected_column_ids": list(resolved_keys),
        "column_order": list(order),
        "preview_version": len(resolved_keys),
    }


async def build_output_preview(
    report_slug: str,
    *,
    selected_column_ids: list[str],
    column_order: list[str],
) -> dict[str, object]:
    slug = canonicalize_report_key(report_slug)
    order = column_order or selected_column_ids

    slug = canonicalize_report_key(report_slug)
    order = column_order or selected_column_ids

    if slug in TOPN_REPORT_SLUGS:
        if slug in {"train-no", "report3"}:
            source_path = await resolve_topn_dataset(slug)
            if source_path is None:
                return {
                    "available": False,
                    "message": NO_DATA_MESSAGE,
                    "selected_count": len(order),
                }
            return build_train_no_preview_rows(
                source_path,
                selected_column_ids=selected_column_ids,
                column_order=order,
            )
        index_path = await resolve_topn_dataset(slug)
        if index_path is None:
            return {
                "available": False,
                "message": NO_DATA_MESSAGE,
                "selected_count": len(order),
            }
        return build_types_preview_rows(
            index_path,
            selected_column_ids=selected_column_ids,
            column_order=order,
        )

    if slug in SCR_NAMESPACED_SLUGS:
        scr_path = await resolve_scr_source_path(slug)
        if scr_path is None:
            return {
                "available": False,
                "message": NO_DATA_MESSAGE,
                "selected_count": len(order),
            }
        return build_scr_preview_rows(
            slug,
            scr_path,
            selected_column_ids=selected_column_ids,
            column_order=order,
        )

    paths = await resolve_source_paths(slug)
    if paths is None:
        return {
            "available": False,
            "message": NO_DATA_MESSAGE,
            "selected_count": len(order),
        }

    merged = build_merged_preview_table(slug, paths[0], paths[1])
    if merged is None:
        return {
            "available": False,
            "message": NO_DATA_MESSAGE,
            "selected_count": len(order),
        }

    merged_headers, merged_rows = merged
    output_headers, output_rows, visible_columns, resolved_keys, _config_source = (
        project_selected_columns(
            merged_headers,
            merged_rows,
            selected_column_ids=selected_column_ids,
            column_order=order,
            report_slug=slug,
            configuration_source="manual_snapshot",
        )
    )

    preview_rows: list[dict[str, str]] = []
    for row in output_rows[:10]:
        preview_rows.append(
            {header: row[idx] if idx < len(row) else "" for idx, header in enumerate(output_headers)}
        )

    return {
        "available": True,
        "report_slug": slug,
        "visible_columns": visible_columns,
        "preview_rows": preview_rows,
        "selected_count": len(resolved_keys),
        "selected_column_ids": list(resolved_keys),
        "column_order": list(order),
        "preview_version": len(resolved_keys),
    }
