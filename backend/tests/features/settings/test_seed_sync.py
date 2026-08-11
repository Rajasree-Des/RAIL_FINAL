"""Seed synchronization: obsolete categories removed, overrides preserved."""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.settings.seeds.default_definitions import DEFAULT_SETTING_DEFINITIONS
from app.infrastructure.seed.seed_app_settings import seed_app_settings
from app.infrastructure.database.models import (
    AppSettingDefinitionModel,
    AppSettingValueModel,
)


@pytest.mark.asyncio
async def test_seed_on_empty_database(test_session: AsyncSession):
    await seed_app_settings(test_session)
    definitions = (
        (await test_session.execute(select(AppSettingDefinitionModel))).scalars().all()
    )
    assert len(definitions) == len(DEFAULT_SETTING_DEFINITIONS)
    assert {d.category for d in definitions} == {"general", "notifications", "account"}


@pytest.mark.asyncio
async def test_seed_sync_removes_obsolete_and_keeps_overrides(
    test_session: AsyncSession,
):
    # Simulate an old install: obsolete category definition with a stored value
    obsolete = AppSettingDefinitionModel(
        category="upload",
        key="max_upload_size_mb",
        label="Maximum Upload Size (MB)",
        value_type="number",
        default_value=json.dumps(50),
        sort_order=1,
        is_editable=True,
    )
    test_session.add(obsolete)
    await test_session.flush()
    test_session.add(
        AppSettingValueModel(definition_id=obsolete.id, value_json=json.dumps(75))
    )

    # Surviving key with a user override
    surviving_seed = next(
        d
        for d in DEFAULT_SETTING_DEFINITIONS
        if d["category"] == "general" and d["key"] == "organization_name"
    )
    surviving = AppSettingDefinitionModel(**surviving_seed)
    test_session.add(surviving)
    await test_session.flush()
    test_session.add(
        AppSettingValueModel(
            definition_id=surviving.id, value_json=json.dumps("My Custom Org")
        )
    )
    await test_session.commit()

    await seed_app_settings(test_session)

    definitions = (
        (await test_session.execute(select(AppSettingDefinitionModel))).scalars().all()
    )
    keys = {(d.category, d.key) for d in definitions}
    assert ("upload", "max_upload_size_mb") not in keys
    assert len(definitions) == len(DEFAULT_SETTING_DEFINITIONS)

    values = (
        (await test_session.execute(select(AppSettingValueModel))).scalars().all()
    )
    assert len(values) == 1
    assert json.loads(values[0].value_json) == "My Custom Org"
    assert values[0].definition_id == surviving.id


@pytest.mark.asyncio
async def test_seed_sync_is_idempotent(test_session: AsyncSession):
    await seed_app_settings(test_session)
    await seed_app_settings(test_session)
    definitions = (
        (await test_session.execute(select(AppSettingDefinitionModel))).scalars().all()
    )
    assert len(definitions) == len(DEFAULT_SETTING_DEFINITIONS)
