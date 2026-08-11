"""Runtime output column configuration resolution and projection."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Literal

from app.automation.processing.output_columns import (
    LEGACY_COLUMN_KEY_ALIASES,
    NAMESPACED_REPORT_SLUGS,
    OutputColumn,
    REPORT1_OUTPUT_COLUMNS,
    REPORT1_SELECTED_KEYS,
    REPORT2_OUTPUT_COLUMNS,
    REPORT2_SELECTED_KEYS,
    REPORT5_OUTPUT_COLUMNS,
    REPORT6_OUTPUT_COLUMNS,
    default_namespaced_keys,
    default_output_column_keys,
    keys_to_output_labels,
    migrate_to_namespaced_ids,
    namespaced_catalog_for_slug,
    namespaced_labels,
    project_merged_table,
    project_merged_table_namespaced,
    select_columns_by_keys,
)
from app.automation.processing.scr_output_columns import (
    SCR_NAMESPACED_SLUGS,
    migrate_scr_to_namespaced_ids,
    project_scr_dict_rows,
    scr_allowed_ids,
    scr_catalog_entries,
    scr_default_ids,
    scr_labels,
    validate_selected_scr_fields,
)
from app.automation.processing.topn_output_columns import (
    TOPN_REPORT_SLUGS,
    ensure_report3_train_no_after_sno,
    migrate_topn_to_namespaced_ids,
    project_topn_canonical_rows,
    topn_allowed_ids,
    topn_catalog_entries,
    topn_default_ids,
    topn_labels,
    validate_selected_topn_fields,
)
from app.automation.comprehensive1013_filters import (
    COMPREHENSIVE_1013_SECTION_IDS,
    SECTION_CONFIGS,
)
from app.automation.processing.comprehensive_output_columns import (
    COMPREHENSIVE_COLUMN_IDS,
    comprehensive_union_column_keys,
    sanitize_comprehensive_section_columns,
    sanitize_comprehensive_sections,
    validate_comprehensive_sections,
)
from app.automation.processing.report14_output_columns import (
    report14_allowed_ids,
    report14_catalog_entries,
    report14_default_ids,
)
from app.automation.processing.report9_output_columns import (
    report9_allowed_ids,
    report9_catalog_entries,
    report9_default_ids,
)
from app.automation.processing.report18_output_columns import (
    report18_allowed_ids,
    report18_catalog_entries,
    report18_default_ids,
)
from app.automation.report_keys import canonicalize_report_key

logger = logging.getLogger(__name__)

COMPREHENSIVE_REPORT_SLUG = "comprehensive-10-13"
REPORT9_SLUG = "report9"
REPORT14_SLUG = "report14"
REPORT18_SLUG = "report18"
BOTTOM_REPORT_SLUG = "bottom-report"

COLUMNLESS_MANUAL_REPORT_SLUGS: frozenset[str] = frozenset({BOTTOM_REPORT_SLUG})


def is_columnless_manual_report(report_slug: str) -> bool:
    return canonicalize_report_key(report_slug) in COLUMNLESS_MANUAL_REPORT_SLUGS


_SECTION_DISPLAY_NAMES: dict[str, str] = {
    section.section_id: section.name for section in SECTION_CONFIGS
}

_SECTION_VALIDATION_NAMES: dict[str, str] = {
    "report10_cw": "Report 10 — C&W",
    "report11_security": "Report 11 — Security",
    "report12_punctuality": "Report 12 — Punctuality",
    "report13_electrical": "Report 13 — Electrical Equipment",
}

ConfigSource = Literal["manual_snapshot", "saved_user_config", "report_default"]

REPORT_OUTPUT_COLUMNS: dict[str, tuple[OutputColumn, ...]] = {
    "report1": REPORT1_OUTPUT_COLUMNS,
    "division": REPORT2_OUTPUT_COLUMNS,
    "scr-train": REPORT5_OUTPUT_COLUMNS,
    "report5": REPORT5_OUTPUT_COLUMNS,
    "scr-station": REPORT6_OUTPUT_COLUMNS,
    "report6_station": REPORT6_OUTPUT_COLUMNS,
}

REPORT_DEFAULT_PROJECTION_KEYS: dict[str, list[str]] = {
    "report1": list(REPORT1_SELECTED_KEYS),
    "division": list(REPORT2_SELECTED_KEYS),
    "scr-train": scr_default_ids("scr-train"),
    "report5": scr_default_ids("scr-train"),
    "scr-station": scr_default_ids("scr-station"),
    "report6_station": scr_default_ids("scr-station"),
    "train-no": topn_default_ids("train-no"),
    "report3": topn_default_ids("train-no"),
    "types": topn_default_ids("types"),
    "report4": topn_default_ids("types"),
    COMPREHENSIVE_REPORT_SLUG: list(COMPREHENSIVE_COLUMN_IDS),
    REPORT9_SLUG: report9_default_ids(),
    REPORT14_SLUG: report14_default_ids(),
    REPORT18_SLUG: report18_default_ids(),
}

_SIMPLE_CATALOG_SLUGS = frozenset({REPORT9_SLUG, REPORT14_SLUG, REPORT18_SLUG})


def _is_scr_slug(slug: str) -> bool:
    return canonicalize_report_key(slug) in SCR_NAMESPACED_SLUGS


def _is_topn_slug(slug: str) -> bool:
    return canonicalize_report_key(slug) in TOPN_REPORT_SLUGS


def _uses_flexible_projection(slug: str) -> bool:
    slug = canonicalize_report_key(slug)
    return (
        slug in NAMESPACED_REPORT_SLUGS
        or slug in SCR_NAMESPACED_SLUGS
        or slug in TOPN_REPORT_SLUGS
        or slug in _SIMPLE_CATALOG_SLUGS
    )

# Backward-compatible label / dataset aliases → canonical output keys (SCR reports)
OUTPUT_COLUMN_KEY_ALIASES: dict[str, str] = {
    **LEGACY_COLUMN_KEY_ALIASES,
    "complaint ref number": "complaintRefNo",
    "created on": "createdOn",
    "train/station": "trainStation",
    "comp type name": "complaintTypeName",
    "sub type name": "subTypeName",
    "zone code": "zoneCode",
    "div code": "divCode",
    "department": "department",
    "status": "status",
    "feedback remark": "feedbackRemark",
    "train name for report": "trainNameForReport",
    "complaint description": "complaintDesc",
    "remarks": "remarks",
    "user id": "userId",
}


def _is_namespaced_report(slug: str) -> bool:
    return canonicalize_report_key(slug) in NAMESPACED_REPORT_SLUGS


def normalize_column_key(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in OUTPUT_COLUMN_KEY_ALIASES:
        return OUTPUT_COLUMN_KEY_ALIASES[lowered]
    if text in OUTPUT_COLUMN_KEY_ALIASES:
        return OUTPUT_COLUMN_KEY_ALIASES[text]
    if text in LEGACY_COLUMN_KEY_ALIASES:
        return LEGACY_COLUMN_KEY_ALIASES[text]
    return text


def migrate_output_column_keys(
    selected: Iterable[str],
    columns: tuple[OutputColumn, ...],
) -> list[str]:
    """Map saved/UI keys to canonical output keys; drop removed fields."""
    migrated: list[str] = []
    seen: set[str] = set()
    valid = {column.key for column in columns}
    for raw in selected:
        key = normalize_column_key(raw)
        if key == "mode" or key == "complaintDate":
            continue
        if key not in valid or key in seen:
            continue
        migrated.append(key)
        seen.add(key)
    return migrated


def merge_saved_column_config(
    selected: Iterable[str],
    columns: tuple[OutputColumn, ...],
) -> list[str]:
    """Preserve user order; append only missing required non-computed keys."""
    migrated = migrate_output_column_keys(selected, columns)
    seen = set(migrated)
    for column in columns:
        if column.computed or not column.required:
            continue
        if column.key not in seen:
            migrated.append(column.key)
            seen.add(column.key)
    return migrated


def sort_keys_by_column_order(
    keys: Iterable[str],
    columns: tuple[OutputColumn, ...],
) -> list[str]:
    order = {column.key: index for index, column in enumerate(columns)}
    return sorted(keys, key=lambda key: order.get(key, len(order)))


def insert_missing_required_in_order(
    selected: Iterable[str],
    columns: tuple[OutputColumn, ...],
) -> list[str]:
    """Preserve user order; insert missing required keys at catalog positions."""
    migrated = migrate_output_column_keys(selected, columns)
    key_order = {column.key: index for index, column in enumerate(columns)}
    seen = set(migrated)
    result = list(migrated)
    for column in columns:
        if column.computed or not column.required or column.key in seen:
            continue
        canonical_idx = key_order[column.key]
        insert_at = len(result)
        for index, key in enumerate(result):
            if key_order.get(key, len(key_order)) > canonical_idx:
                insert_at = index
                break
        result.insert(insert_at, column.key)
        seen.add(column.key)
    return result


def finalize_output_keys(
    selected: Iterable[str],
    columns: tuple[OutputColumn, ...],
    *,
    preserve_user_order: bool = True,
) -> list[str]:
    """Migrate legacy keys and ensure mandatory fields are present (UI catalog only)."""
    if preserve_user_order:
        return insert_missing_required_in_order(selected, columns)
    merged = merge_saved_column_config(selected, columns)
    return sort_keys_by_column_order(merged, columns)


def _allowed_projection_keys(slug: str) -> frozenset[str]:
    slug = canonicalize_report_key(slug)
    if slug in NAMESPACED_REPORT_SLUGS:
        catalog = namespaced_catalog_for_slug(slug)
        return frozenset(col.id for col in catalog)
    if slug in SCR_NAMESPACED_SLUGS:
        return scr_allowed_ids(slug)
    if slug in TOPN_REPORT_SLUGS:
        return topn_allowed_ids(slug)
    if slug == REPORT9_SLUG:
        return report9_allowed_ids()
    if slug == REPORT14_SLUG:
        return report14_allowed_ids()
    if slug == REPORT18_SLUG:
        return report18_allowed_ids()
    defaults = REPORT_DEFAULT_PROJECTION_KEYS.get(slug)
    if defaults is None:
        return frozenset()
    return frozenset(defaults)


def sanitize_projection_keys(
    selected: Iterable[str],
    report_slug: str,
    *,
    user_id: str | None = None,
) -> list[str]:
    """Migrate and filter to allowed projection keys; preserve order; never append extras."""
    slug = canonicalize_report_key(report_slug)
    allowed = _allowed_projection_keys(slug)
    if not allowed:
        return []

    if slug in NAMESPACED_REPORT_SLUGS:
        migrated = migrate_to_namespaced_ids(slug, selected)
        return [key for key in migrated if key in allowed]

    if slug in SCR_NAMESPACED_SLUGS:
        migrated = migrate_scr_to_namespaced_ids(slug, selected)
        return [key for key in migrated if key in allowed]

    if slug in TOPN_REPORT_SLUGS:
        migrated = migrate_topn_to_namespaced_ids(slug, selected)
        return [key for key in migrated if key in allowed]

    sanitized: list[str] = []
    seen: set[str] = set()
    for raw in selected:
        key = normalize_column_key(str(raw))
        if key == "mode" or key == "complaintDate":
            continue
        if key in allowed and key not in seen:
            sanitized.append(key)
            seen.add(key)
    return sanitized


def validate_projection_selection(report_slug: str, keys: list[str]) -> None:
    """Raise ValueError when resolved projection keys are invalid for the report."""
    slug = canonicalize_report_key(report_slug)

    if _uses_flexible_projection(slug):
        allowed = _allowed_projection_keys(slug)
        if len(keys) < 1:
            raise ValueError(f"Report {slug} requires at least one selected column")
        if len(keys) != len(set(keys)):
            raise ValueError(f"Report {slug} selected columns contain duplicates")
        invalid = [key for key in keys if key not in allowed]
        if invalid:
            raise ValueError(
                f"Report {slug} selected columns must belong to the approved allowlist. "
                f"invalid={sorted(invalid)}"
            )
        if slug in SCR_NAMESPACED_SLUGS:
            wrong_prefix = [key for key in keys if not key.startswith(f"{slug}.")]
            if wrong_prefix:
                raise ValueError(
                    f"Report {slug} selected columns must use namespaced IDs for this report. "
                    f"invalid={sorted(wrong_prefix)}"
                )
        if slug in TOPN_REPORT_SLUGS:
            expected_prefix = "train-no." if slug in {"train-no", "report3"} else "types."
            cross_prefix = [
                key
                for key in keys
                if key.startswith("train-no.") and slug in {"types", "report4"}
                or key.startswith("types.") and slug in {"train-no", "report3"}
            ]
            if cross_prefix:
                raise ValueError(
                    f"Report {slug} selected columns must not use IDs from another report. "
                    f"invalid={sorted(cross_prefix)}"
                )
            wrong_prefix = [key for key in keys if not key.startswith(expected_prefix)]
            if wrong_prefix:
                raise ValueError(
                    f"Report {slug} selected columns must use namespaced IDs for this report. "
                    f"invalid={sorted(wrong_prefix)}"
                )
        return


def validate_column_order(
    report_slug: str,
    selected_column_ids: list[str],
    column_order: list[str],
) -> None:
    """Ensure column_order is a permutation of selected_column_ids."""
    slug = canonicalize_report_key(report_slug)
    if is_columnless_manual_report(slug):
        return
    validate_projection_selection(slug, selected_column_ids)
    if set(column_order) != set(selected_column_ids):
        raise ValueError(
            f"Report {slug} column_order must contain every selected column exactly once"
        )
    if len(column_order) != len(selected_column_ids):
        raise ValueError(f"Report {slug} column_order length mismatch")


def _keys_from_manual_config(
    manual: dict[str, Any],
    slug: str,
    *,
    user_id: str | None = None,
) -> list[str] | None:
    manual_slug = canonicalize_report_key(str(manual.get("report_slug") or slug))
    if manual_slug != slug:
        return None
    order = manual.get("column_order") or manual.get("selected_column_ids")
    if not order:
        return None
    keys = sanitize_projection_keys(order, slug, user_id=user_id)
    return keys if keys else None


def resolve_projection_column_keys(
    report_slug: str,
    *,
    user_id: str | None = None,
    column_selection: dict[str, Any] | None = None,
) -> tuple[list[str], ConfigSource]:
    """Precedence: explicit snapshot → run manual_config → saved config → defaults."""
    slug = canonicalize_report_key(report_slug)
    defaults = REPORT_DEFAULT_PROJECTION_KEYS.get(slug)
    if not defaults:
        return [], "report_default"

    from app.automation.run_context import get_run_context
    from app.features.reports.config_store import load_report_config

    ctx = get_run_context()
    run_id = ctx.run_id if ctx else None
    effective_user_id = user_id or (ctx.user_id if ctx else None)

    received = column_selection or (ctx.manual_config if ctx else None) or {}
    if received:
        keys = _keys_from_manual_config(received, slug, user_id=effective_user_id)
        if keys:
            if slug == "train-no":
                keys = ensure_report3_train_no_after_sno(keys, slug)
            _log_projection(run_id, slug, keys, "manual_snapshot", received_from_frontend=keys)
            return keys, "manual_snapshot"

    saved = load_report_config(slug, user_id=effective_user_id)
    if saved:
        order = (
            saved.get("default_selected_column_ids")
            or saved.get("column_order")
            or saved.get("selected_column_ids")
        )
        if order:
            keys = sanitize_projection_keys(order, slug, user_id=effective_user_id)
            if keys:
                if slug == "train-no":
                    keys = ensure_report3_train_no_after_sno(keys, slug)
                _log_projection(run_id, slug, keys, "saved_user_config")
                return keys, "saved_user_config"

    keys = list(defaults)
    if slug == "train-no":
        keys = ensure_report3_train_no_after_sno(keys, slug)
    _log_projection(run_id, slug, keys, "report_default")
    return keys, "report_default"


def _log_projection(
    run_id: str | None,
    slug: str,
    keys: list[str],
    source: ConfigSource,
    *,
    received_from_frontend: list[str] | None = None,
) -> None:
    if slug in NAMESPACED_REPORT_SLUGS:
        labels = namespaced_labels(keys, slug)
    elif slug in SCR_NAMESPACED_SLUGS:
        labels = scr_labels(keys, slug)
    elif slug in TOPN_REPORT_SLUGS:
        labels = topn_labels(keys, slug)
    else:
        columns = REPORT_OUTPUT_COLUMNS.get(slug)
        labels = keys_to_output_labels(keys, columns) if columns else keys
    logger.info(
        "output_columns_projection run_id=%s report_slug=%s configuration_source=%s "
        "columns_received_from_frontend=%s columns_resolved_for_run=%s "
        "selected_column_ids=%s selected_column_labels=%s selected_column_count=%d snapshot_saved=%s",
        run_id,
        slug,
        source,
        received_from_frontend if received_from_frontend is not None else keys,
        keys,
        keys,
        labels,
        len(keys),
        source == "manual_snapshot",
    )


def final_output_column_keys(report_slug: str) -> list[str]:
    """Fixed projection keys for SCR reports; R1/R2 use resolve_projection_column_keys."""
    slug = canonicalize_report_key(report_slug)
    if slug in REPORT_DEFAULT_PROJECTION_KEYS:
        return list(REPORT_DEFAULT_PROJECTION_KEYS[slug])
    columns = REPORT_OUTPUT_COLUMNS.get(slug)
    if columns is None:
        return []
    return default_output_column_keys(columns)


def resolve_effective_column_keys(report_slug: str) -> list[str]:
    """UI/catalog resolution — returns saved or default selection without auto-expansion."""
    slug = canonicalize_report_key(report_slug)

    if slug in NAMESPACED_REPORT_SLUGS:
        keys, _source = resolve_projection_column_keys(slug)
        return keys if keys else default_namespaced_keys(slug)

    if slug in SCR_NAMESPACED_SLUGS:
        keys, _source = resolve_projection_column_keys(slug)
        return keys if keys else scr_default_ids(slug)

    if slug in TOPN_REPORT_SLUGS:
        keys, _source = resolve_projection_column_keys(slug)
        return keys if keys else topn_default_ids(slug)

    columns = REPORT_OUTPUT_COLUMNS.get(slug)
    if columns is None:
        return []

    from app.automation.run_context import get_run_context
    from app.features.reports.config_store import load_report_config

    ctx = get_run_context()
    manual = (ctx.manual_config or {}) if ctx else {}
    manual_slug = canonicalize_report_key(str(manual.get("report_slug") or slug))
    if manual and manual_slug == slug:
        order = manual.get("column_order") or manual.get("selected_column_ids")
        if order:
            return finalize_output_keys(order, columns, preserve_user_order=True)

    saved = load_report_config(slug, user_id=ctx.user_id if ctx else None)
    if saved:
        order = (
            saved.get("default_selected_column_ids")
            or saved.get("column_order")
            or saved.get("selected_column_ids")
        )
        if order:
            return finalize_output_keys(order, columns, preserve_user_order=False)

    return list(REPORT_DEFAULT_PROJECTION_KEYS.get(slug, default_output_column_keys(columns)))


def resolve_output_labels(report_slug: str) -> list[str]:
    slug = canonicalize_report_key(report_slug)
    keys, _source = resolve_projection_column_keys(slug)
    if slug in NAMESPACED_REPORT_SLUGS:
        return namespaced_labels(keys, slug)
    if slug in SCR_NAMESPACED_SLUGS:
        return scr_labels(keys, slug)
    columns = REPORT_OUTPUT_COLUMNS.get(slug)
    if not columns:
        return []
    return keys_to_output_labels(keys, columns)


def project_for_output(
    report_slug: str,
    *,
    full_headers: list[str],
    rows: list[list[str]],
    selected_keys: list[str] | None = None,
    config_source: ConfigSource | None = None,
    column_selection: dict[str, Any] | None = None,
) -> tuple[list[str], list[list[str]], list[str], list[str], ConfigSource]:
    slug = canonicalize_report_key(report_slug)
    if selected_keys is not None:
        keys = sanitize_projection_keys(selected_keys, slug)
        source = config_source or "manual_snapshot"
    else:
        keys, source = resolve_projection_column_keys(slug, column_selection=column_selection)

    if slug in NAMESPACED_REPORT_SLUGS:
        validate_projection_selection(slug, keys)
        report_label = f"Report {slug}"
        out_headers, out_rows = project_merged_table_namespaced(
            full_headers,
            rows,
            keys,
            report_slug=slug,
            report_label=report_label,
        )
        labels = namespaced_labels(keys, slug)
        return out_headers, out_rows, labels, keys, source

    columns = REPORT_OUTPUT_COLUMNS.get(slug)
    if not columns:
        return full_headers, rows, full_headers, [], "report_default"
    validate_projection_selection(slug, keys)
    report_label = f"Report {slug}"
    out_headers, out_rows = project_merged_table(
        full_headers,
        rows,
        keys,
        columns,
        report_label=report_label,
    )
    labels = keys_to_output_labels(keys, columns)
    return out_headers, out_rows, labels, keys, source


def project_selected_columns(
    full_headers: list[str],
    rows: list[list[str]],
    *,
    selected_column_ids: list[str],
    column_order: list[str] | None,
    report_slug: str,
    configuration_source: ConfigSource | None = None,
) -> tuple[list[str], list[list[str]], list[str], list[str], ConfigSource]:
    """Shared projection entry for preview and generation."""
    slug = canonicalize_report_key(report_slug)
    if is_columnless_manual_report(slug):
        return full_headers, rows, full_headers, [], configuration_source or "report_default"
    order = column_order or selected_column_ids
    keys = sanitize_projection_keys(order, slug)
    validate_column_order(slug, keys, list(order))
    return project_for_output(
        slug,
        full_headers=full_headers,
        rows=rows,
        selected_keys=keys,
        config_source=configuration_source or "manual_snapshot",
    )


def scr_columns_for_run(report_slug: str) -> tuple[OutputColumn, ...]:
    slug = canonicalize_report_key(report_slug)
    columns = REPORT_OUTPUT_COLUMNS.get(slug)
    if not columns:
        return ()
    keys, _source = resolve_projection_column_keys(slug)
    validate_projection_selection(slug, keys)
    return select_columns_by_keys(columns, keys)


def projection_labels_for_slug(report_slug: str, selected_ids: Iterable[str]) -> list[str]:
    """Resolve display labels for selected projection IDs (R1/R2 namespaced or SCR)."""
    slug = canonicalize_report_key(report_slug)
    keys = list(selected_ids)
    if slug in SCR_NAMESPACED_SLUGS:
        return scr_labels(keys, slug)
    if slug in TOPN_REPORT_SLUGS:
        return topn_labels(keys, slug)
    if slug in NAMESPACED_REPORT_SLUGS:
        return namespaced_labels(keys, slug)
    columns = REPORT_OUTPUT_COLUMNS.get(slug)
    if columns:
        return keys_to_output_labels(keys, columns)
    return keys


def project_scr_for_output(
    report_slug: str,
    rows: list[dict[str, str]],
    *,
    selected_keys: list[str] | None = None,
    config_source: ConfigSource | None = None,
    column_selection: dict[str, Any] | None = None,
) -> tuple[list[str], list[list[str]], list[str], list[str], ConfigSource]:
    slug = canonicalize_report_key(report_slug)
    if selected_keys is not None:
        keys = sanitize_projection_keys(selected_keys, slug)
        source = config_source or "manual_snapshot"
    else:
        keys, source = resolve_projection_column_keys(slug, column_selection=column_selection)
    validate_projection_selection(slug, keys)
    unavailable = validate_selected_scr_fields(rows, keys, slug)
    if unavailable:
        raise ValueError(
            f"SELECTED_COLUMN_UNAVAILABLE: missing source fields for {sorted(unavailable)}"
        )
    try:
        out_headers, out_rows = project_scr_dict_rows(rows, keys, slug)
    except ValueError as exc:
        raise ValueError(f"COLUMN_PROJECTION_FAILED: {exc}") from exc
    labels = scr_labels(keys, slug)
    return out_headers, out_rows, labels, keys, source


def project_topn_for_output(
    report_slug: str,
    canonical_rows: list[dict[str, str]],
    *,
    selected_keys: list[str] | None = None,
    config_source: ConfigSource | None = None,
    column_selection: dict[str, Any] | None = None,
) -> tuple[list[str], list[list[str]], list[str], list[str], ConfigSource]:
    slug = canonicalize_report_key(report_slug)
    if selected_keys is not None:
        keys = sanitize_projection_keys(selected_keys, slug)
        source = config_source or "manual_snapshot"
    else:
        keys, source = resolve_projection_column_keys(slug, column_selection=column_selection)
    validate_projection_selection(slug, keys)
    unavailable = validate_selected_topn_fields(canonical_rows, keys, slug)
    if unavailable:
        raise ValueError(
            f"SELECTED_COLUMN_UNAVAILABLE: missing source fields for {sorted(unavailable)}"
        )
    try:
        out_headers, out_rows = project_topn_canonical_rows(canonical_rows, keys, slug)
    except ValueError as exc:
        raise ValueError(f"COLUMN_PROJECTION_FAILED: {exc}") from exc
    keys = ensure_report3_train_no_after_sno(keys, slug)
    labels = topn_labels(keys, slug)
    return out_headers, out_rows, labels, keys, source


def extract_comprehensive_sections_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Read sections from a generate/save payload or legacy nested overrides."""
    sections = payload.get("sections")
    if isinstance(sections, dict) and sections:
        return sections
    overrides = payload.get("config_overrides")
    if isinstance(overrides, dict):
        nested = overrides.get("sections")
        if isinstance(nested, dict) and nested:
            return nested
        column_selection = overrides.get("column_selection")
        if isinstance(column_selection, dict):
            legacy = column_selection.get("sections")
            if isinstance(legacy, dict) and legacy:
                return legacy
    return None


def output_column_catalog(report_slug: str) -> list[dict[str, object]]:
    slug = canonicalize_report_key(report_slug)
    if slug in TOPN_REPORT_SLUGS:
        return topn_catalog_entries(slug)
    if slug in SCR_NAMESPACED_SLUGS:
        return scr_catalog_entries(slug)
    if slug in NAMESPACED_REPORT_SLUGS:
        defaults = set(REPORT_DEFAULT_PROJECTION_KEYS.get(slug, []))
        group_titles = {
            "source_a": (
                "Source A — Comprehensive"
                if slug == "report1"
                else "Source A — Comprehensive Division Wise"
            ),
            "source_b": (
                "Source B — Feedback"
                if slug == "report1"
                else "Source B — Feedback Division Wise"
            ),
        }
        return [
            {
                "id": column.id,
                "label": column.label,
                "group": column.group,
                "group_title": group_titles.get(column.group, column.group),
                "required": False,
                "default_visible": column.id in defaults,
            }
            for column in namespaced_catalog_for_slug(slug)
        ]

    if slug == COMPREHENSIVE_REPORT_SLUG:
        from app.automation.processing.comprehensive_output_columns import COMPREHENSIVE_COLUMN_LABELS

        defaults = set(COMPREHENSIVE_COLUMN_IDS)
        return [
            {
                "id": col_id,
                "label": COMPREHENSIVE_COLUMN_LABELS[col_id],
                "group": "comprehensive",
                "group_title": "Comprehensive Reports",
                "required": False,
                "default_visible": col_id in defaults,
            }
            for col_id in COMPREHENSIVE_COLUMN_IDS
        ]

    if slug == REPORT9_SLUG:
        return report9_catalog_entries()

    if slug == REPORT14_SLUG:
        return report14_catalog_entries()

    if slug == REPORT18_SLUG:
        return report18_catalog_entries()

    return []
