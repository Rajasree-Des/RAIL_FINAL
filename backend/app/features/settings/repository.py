"""Data access for application settings."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.json_utils import deserialize_json, serialize_json
from app.infrastructure.database.models import AppSettingDefinitionModel, AppSettingValueModel


class SettingsRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def deserialize(raw: str | None) -> Any:
        return deserialize_json(raw)

    @staticmethod
    def serialize(value: Any) -> str:
        return serialize_json(value)

    async def list_definitions(
        self,
        category: str | None = None,
    ) -> list[AppSettingDefinitionModel]:
        stmt = select(AppSettingDefinitionModel).options(
            selectinload(AppSettingDefinitionModel.value)
        )
        if category:
            stmt = stmt.where(AppSettingDefinitionModel.category == category)
        stmt = stmt.order_by(
            AppSettingDefinitionModel.category,
            AppSettingDefinitionModel.sort_order,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_definition(
        self,
        category: str,
        key: str,
    ) -> AppSettingDefinitionModel | None:
        stmt = (
            select(AppSettingDefinitionModel)
            .options(selectinload(AppSettingDefinitionModel.value))
            .where(
                AppSettingDefinitionModel.category == category,
                AppSettingDefinitionModel.key == key,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_value(
        self,
        definition_id: str,
        value: Any,
        user_id: str | None = None,
    ) -> AppSettingValueModel:
        stmt = select(AppSettingValueModel).where(
            AppSettingValueModel.definition_id == definition_id
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        serialized = self.serialize(value)

        if existing:
            existing.value_json = serialized
            existing.updated_by = user_id
            await self._session.commit()
            await self._session.refresh(existing)
            return existing

        model = AppSettingValueModel(
            definition_id=definition_id,
            value_json=serialized,
            updated_by=user_id,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return model

    async def delete_value(self, definition_id: str) -> None:
        stmt = select(AppSettingValueModel).where(
            AppSettingValueModel.definition_id == definition_id
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            await self._session.delete(existing)
            await self._session.commit()

    async def reset_category(self, category: str) -> int:
        definitions = await self.list_definitions(category=category)
        count = 0
        for definition in definitions:
            if definition.value:
                await self._session.delete(definition.value)
                count += 1
        if count:
            await self._session.commit()
        return count
