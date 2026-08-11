"""Synchronize application setting definitions with the code defaults.

Inserts missing definitions and removes obsolete ones (values cascade),
while preserving user overrides for definitions that still exist.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.settings.seeds.default_definitions import DEFAULT_SETTING_DEFINITIONS
from app.infrastructure.database.models import (
    AppSettingDefinitionModel,
    AppSettingValueModel,
)


async def seed_app_settings(session: AsyncSession) -> None:
    """Sync setting definitions: add new, drop removed, keep overrides."""
    existing = list(
        (await session.execute(select(AppSettingDefinitionModel))).scalars().all()
    )
    existing_by_key = {(d.category, d.key): d for d in existing}
    wanted_keys = {(d["category"], d["key"]) for d in DEFAULT_SETTING_DEFINITIONS}

    changed = False

    # Remove definitions no longer in the defaults (their values cascade)
    obsolete_ids = [
        d.id for (cat, key), d in existing_by_key.items() if (cat, key) not in wanted_keys
    ]
    if obsolete_ids:
        await session.execute(
            delete(AppSettingValueModel).where(
                AppSettingValueModel.definition_id.in_(obsolete_ids)
            )
        )
        await session.execute(
            delete(AppSettingDefinitionModel).where(
                AppSettingDefinitionModel.id.in_(obsolete_ids)
            )
        )
        changed = True

    # Insert new definitions and refresh metadata of existing ones
    for definition in DEFAULT_SETTING_DEFINITIONS:
        current = existing_by_key.get((definition["category"], definition["key"]))
        if current is None:
            session.add(AppSettingDefinitionModel(**definition))
            changed = True
            continue
        for field in (
            "label",
            "description",
            "value_type",
            "default_value",
            "validation_json",
            "options_json",
            "sort_order",
            "is_editable",
        ):
            if getattr(current, field) != definition[field]:
                setattr(current, field, definition[field])
                changed = True

    if changed:
        await session.commit()
