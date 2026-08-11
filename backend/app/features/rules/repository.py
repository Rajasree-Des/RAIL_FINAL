"""Repository layer for Business Rules Engine."""

import json
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import ConfigurableRuleModel


class RuleRepository:
    """Repository for ConfigurableRule CRUD operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_all(
        self,
        template_id: str | None = None,
        category: str | None = None,
        is_enabled: bool | None = None,
        include_deleted: bool = False,
        include_global: bool = True,
    ) -> list[ConfigurableRuleModel]:
        """List rules with optional filtering."""
        query = select(ConfigurableRuleModel)

        if not include_deleted:
            query = query.where(ConfigurableRuleModel.is_deleted == False)  # noqa: E712

        if template_id is not None:
            if include_global:
                query = query.where(
                    or_(
                        ConfigurableRuleModel.template_id == template_id,
                        ConfigurableRuleModel.is_global == True,  # noqa: E712
                    )
                )
            else:
                query = query.where(ConfigurableRuleModel.template_id == template_id)

        if category is not None:
            query = query.where(ConfigurableRuleModel.category == category)

        if is_enabled is not None:
            query = query.where(ConfigurableRuleModel.is_enabled == is_enabled)

        query = query.order_by(
            ConfigurableRuleModel.category,
            ConfigurableRuleModel.priority,
            ConfigurableRuleModel.name,
        )

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, rule_id: str) -> ConfigurableRuleModel | None:
        """Get a rule by ID."""
        query = (
            select(ConfigurableRuleModel)
            .where(ConfigurableRuleModel.id == rule_id)
            .where(ConfigurableRuleModel.is_deleted == False)  # noqa: E712
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_template(
        self,
        template_id: str,
        include_global: bool = True,
    ) -> list[ConfigurableRuleModel]:
        """Get all rules for a template."""
        return await self.list_all(
            template_id=template_id,
            is_enabled=True,
            include_global=include_global,
        )

    async def get_by_category(
        self,
        template_id: str,
        category: str,
    ) -> list[ConfigurableRuleModel]:
        """Get rules for a template filtered by category."""
        return await self.list_all(
            template_id=template_id,
            category=category,
            is_enabled=True,
        )

    async def create(
        self,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> ConfigurableRuleModel:
        """Create a new rule."""
        config = data.pop("config", {})
        conditions = data.pop("conditions", None)

        rule = ConfigurableRuleModel(
            **data,
            config_json=json.dumps(config),
            conditions_json=json.dumps(conditions) if conditions else None,
            created_by=user_id,
            updated_by=user_id,
        )
        self._session.add(rule)
        await self._session.commit()
        await self._session.refresh(rule)
        return rule

    async def update(
        self,
        rule_id: str,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> ConfigurableRuleModel | None:
        """Update an existing rule."""
        rule = await self.get_by_id(rule_id)
        if not rule:
            return None

        if "config" in data:
            data["config_json"] = json.dumps(data.pop("config"))

        if "conditions" in data:
            conditions = data.pop("conditions")
            data["conditions_json"] = json.dumps(conditions) if conditions else None

        for key, value in data.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        rule.updated_by = user_id

        await self._session.commit()
        await self._session.refresh(rule)
        return rule

    async def delete(
        self,
        rule_id: str,
        user_id: str | None = None,
    ) -> bool:
        """Soft delete a rule."""
        stmt = (
            update(ConfigurableRuleModel)
            .where(ConfigurableRuleModel.id == rule_id)
            .where(ConfigurableRuleModel.is_deleted == False)  # noqa: E712
            .values(is_deleted=True, updated_by=user_id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0

    async def toggle_enabled(
        self,
        rule_id: str,
        user_id: str | None = None,
    ) -> ConfigurableRuleModel | None:
        """Toggle the enabled status of a rule."""
        rule = await self.get_by_id(rule_id)
        if not rule:
            return None

        rule.is_enabled = not rule.is_enabled
        rule.updated_by = user_id

        await self._session.commit()
        await self._session.refresh(rule)
        return rule

    async def duplicate(
        self,
        rule_id: str,
        new_name: str,
        user_id: str | None = None,
    ) -> ConfigurableRuleModel | None:
        """Duplicate a rule with a new name."""
        original = await self.get_by_id(rule_id)
        if not original:
            return None

        new_rule = ConfigurableRuleModel(
            name=new_name,
            description=original.description,
            template_id=original.template_id,
            category=original.category,
            rule_type=original.rule_type,
            config_json=original.config_json,
            priority=original.priority,
            group_id=original.group_id,
            is_enabled=False,
            is_global=original.is_global,
            conditions_json=original.conditions_json,
            created_by=user_id,
            updated_by=user_id,
        )
        self._session.add(new_rule)
        await self._session.commit()
        await self._session.refresh(new_rule)
        return new_rule

    async def reorder(
        self,
        rule_priorities: list[dict[str, Any]],
        user_id: str | None = None,
    ) -> int:
        """Update priorities for multiple rules."""
        updated_count = 0
        for item in rule_priorities:
            rule_id = item.get("id")
            priority = item.get("priority")
            if rule_id and priority is not None:
                stmt = (
                    update(ConfigurableRuleModel)
                    .where(ConfigurableRuleModel.id == rule_id)
                    .where(ConfigurableRuleModel.is_deleted == False)  # noqa: E712
                    .values(priority=priority, updated_by=user_id)
                )
                result = await self._session.execute(stmt)
                updated_count += result.rowcount

        await self._session.commit()
        return updated_count

    async def bulk_toggle(
        self,
        rule_ids: list[str],
        is_enabled: bool,
        user_id: str | None = None,
    ) -> int:
        """Enable or disable multiple rules."""
        stmt = (
            update(ConfigurableRuleModel)
            .where(ConfigurableRuleModel.id.in_(rule_ids))
            .where(ConfigurableRuleModel.is_deleted == False)  # noqa: E712
            .values(is_enabled=is_enabled, updated_by=user_id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount

    async def bulk_delete(
        self,
        rule_ids: list[str],
        user_id: str | None = None,
    ) -> int:
        """Soft delete multiple rules."""
        stmt = (
            update(ConfigurableRuleModel)
            .where(ConfigurableRuleModel.id.in_(rule_ids))
            .where(ConfigurableRuleModel.is_deleted == False)  # noqa: E712
            .values(is_deleted=True, updated_by=user_id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount
