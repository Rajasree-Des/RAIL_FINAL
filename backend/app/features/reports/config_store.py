"""Persist saved report configuration for future runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.automation.processing.column_config import (
    COMPREHENSIVE_REPORT_SLUG,
    sanitize_comprehensive_sections,
    sanitize_projection_keys,
)
from app.automation.processing.comprehensive_output_columns import COMPREHENSIVE_COLUMN_IDS
from app.automation.processing.output_columns import (
    NAMESPACED_REPORT_SLUGS,
    REPORT1_DEFAULT_NAMESPACED_KEYS,
    REPORT2_DEFAULT_NAMESPACED_KEYS,
    migrate_to_namespaced_ids,
)
from app.automation.processing.scr_output_columns import (
    SCR_NAMESPACED_SLUGS,
    scr_default_ids,
)
from app.automation.processing.topn_output_columns import TOPN_REPORT_SLUGS, topn_default_ids
from app.automation.processing.report9_output_columns import report9_default_ids
from app.automation.processing.report14_output_columns import report14_default_ids
from app.automation.processing.report18_output_columns import report18_default_ids
from app.automation.report_keys import canonicalize_report_key

CONFIG_DIR = Path("storage") / "report-configs"

_DEFAULT_PROJECTION_KEYS: dict[str, list[str]] = {
    "report1": list(REPORT1_DEFAULT_NAMESPACED_KEYS),
    "division": list(REPORT2_DEFAULT_NAMESPACED_KEYS),
    "scr-train": scr_default_ids("scr-train"),
    "report5": scr_default_ids("scr-train"),
    "scr-station": scr_default_ids("scr-station"),
    "report6_station": scr_default_ids("scr-station"),
    "train-no": topn_default_ids("train-no"),
    "report3": topn_default_ids("train-no"),
    "types": topn_default_ids("types"),
    "report4": topn_default_ids("types"),
    COMPREHENSIVE_REPORT_SLUG: list(COMPREHENSIVE_COLUMN_IDS),
    "report9": report9_default_ids(),
    "report14": report14_default_ids(),
    "report18": report18_default_ids(),
    "bottom-report": [],
}

_PER_USER_SLUGS = NAMESPACED_REPORT_SLUGS | SCR_NAMESPACED_SLUGS | TOPN_REPORT_SLUGS


def config_path(report_slug: str, user_id: str | None = None) -> Path:
    slug = canonicalize_report_key(report_slug)
    if slug in _PER_USER_SLUGS and user_id:
        return CONFIG_DIR / user_id / f"{slug}.json"
    if slug in _PER_USER_SLUGS:
        return CONFIG_DIR / f"{slug}.json"
    return CONFIG_DIR / f"{slug}.json"


def _valid_projection_keys(report_slug: str, keys: list[str]) -> bool:
    slug = canonicalize_report_key(report_slug)
    if slug in _PER_USER_SLUGS:
        sanitized = sanitize_projection_keys(keys, slug)
        return len(sanitized) >= 1 and len(sanitized) == len(set(sanitized))
    return True


def _migrate_column_keys(
    report_slug: str,
    payload: dict[str, Any],
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    slug = canonicalize_report_key(report_slug)
    migrated = dict(payload)

    if slug == COMPREHENSIVE_REPORT_SLUG:
        sections = migrated.get("sections")
        if isinstance(sections, dict) and sections:
            from app.automation.processing.comprehensive_output_columns import (
                build_comprehensive_column_snapshot,
            )

            try:
                column_snapshot = build_comprehensive_column_snapshot(
                    sections,
                    date_from=str(migrated.get("date_from") or "") or None,
                    date_to=str(migrated.get("date_to") or "") or None,
                )
            except ValueError:
                column_snapshot = None
            if column_snapshot:
                migrated.update(
                    {
                        "sections": column_snapshot["sections"],
                        "selected_column_ids": column_snapshot["selected_column_ids"],
                        "column_order": column_snapshot["column_order"],
                        "snapshot_hash": column_snapshot["snapshot_hash"],
                        "version": column_snapshot["version"],
                    }
                )
        return migrated

    defaults = _DEFAULT_PROJECTION_KEYS.get(slug)
    if defaults is None:
        return payload
    migrated = dict(payload)
    for key in ("column_order", "selected_column_ids", "default_selected_column_ids"):
        order = migrated.get(key)
        if not order:
            continue
        if slug in NAMESPACED_REPORT_SLUGS:
            sanitized = migrate_to_namespaced_ids(slug, order)
            sanitized = sanitize_projection_keys(sanitized, slug, user_id=user_id)
        elif slug in TOPN_REPORT_SLUGS:
            from app.automation.processing.topn_output_columns import migrate_topn_to_namespaced_ids

            sanitized = migrate_topn_to_namespaced_ids(slug, order)
            sanitized = sanitize_projection_keys(sanitized, slug, user_id=user_id)
        else:
            sanitized = sanitize_projection_keys(order, slug, user_id=user_id)
        if _valid_projection_keys(slug, sanitized):
            migrated[key] = sanitized
        else:
            migrated[key] = list(defaults)
    return migrated


def save_report_config(
    report_slug: str,
    payload: dict[str, Any],
    *,
    user_id: str | None = None,
) -> None:
    slug = canonicalize_report_key(report_slug)
    path = config_path(slug, user_id=user_id if slug in _PER_USER_SLUGS else None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _migrate_column_keys(slug, payload, user_id=user_id),
            indent=2,
        ),
        encoding="utf-8",
    )


def default_projection_keys(report_slug: str) -> list[str]:
    slug = canonicalize_report_key(report_slug)
    defaults = _DEFAULT_PROJECTION_KEYS.get(slug)
    return list(defaults) if defaults else []


def load_report_config(
    report_slug: str,
    *,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    slug = canonicalize_report_key(report_slug)
    candidates: list[Path] = []
    if slug in _PER_USER_SLUGS and user_id:
        candidates.append(config_path(slug, user_id=user_id))
    candidates.append(config_path(slug))
    if slug in _PER_USER_SLUGS:
        candidates.append(CONFIG_DIR / f"{slug}.json")
    legacy_aliases = {
        "train-no": "report3",
        "types": "report4",
        "scr-train": "report5",
        "scr-station": "report6_station",
    }
    legacy = legacy_aliases.get(slug)
    if legacy:
        if user_id:
            candidates.append(CONFIG_DIR / user_id / f"{legacy}.json")
        candidates.append(CONFIG_DIR / f"{legacy}.json")

    for path in candidates:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        return _migrate_column_keys(slug, payload, user_id=user_id)
    return None
