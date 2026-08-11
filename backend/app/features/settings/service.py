"""Application settings business logic."""

from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.features.settings.cache import CACHE_KEY_ALL, settings_cache
from app.features.settings.repository import SettingsRepository
from app.features.settings.schemas import (
    DisplaySettingsResponse,
    SettingCategorySchema,
    SettingItemSchema,
    SettingOptionSchema,
    SettingsExportResponse,
    SettingsImportResponse,
    SettingsResponse,
    SettingsUpdateResponse,
)
from app.features.settings.seeds.default_definitions import SETTING_CATEGORIES
from app.features.settings.validator import parse_json_field, validate_setting_value
from app.infrastructure.database.models import AppSettingDefinitionModel


class SettingsService:
    CATEGORY_LABELS = {c["slug"]: c for c in SETTING_CATEGORIES}

    def __init__(self, repository: SettingsRepository):
        self.repository = repository

    def _effective_value(self, definition: AppSettingDefinitionModel) -> tuple[Any, bool]:
        default = self.repository.deserialize(definition.default_value)
        if definition.value:
            return self.repository.deserialize(definition.value.value_json), True
        return default, False

    def _to_item(self, definition: AppSettingDefinitionModel) -> SettingItemSchema:
        value, is_modified = self._effective_value(definition)
        validation = parse_json_field(definition.validation_json)
        options_raw = parse_json_field(definition.options_json)
        options = (
            [SettingOptionSchema(**opt) for opt in options_raw]
            if options_raw
            else None
        )
        return SettingItemSchema(
            id=definition.id,
            category=definition.category,
            key=definition.key,
            label=definition.label,
            description=definition.description,
            value_type=definition.value_type,
            value=value,
            default_value=self.repository.deserialize(definition.default_value),
            validation=validation if isinstance(validation, dict) else None,
            options=options,
            sort_order=definition.sort_order,
            is_editable=definition.is_editable,
            is_modified=is_modified,
        )

    def _build_response(self, definitions: list[AppSettingDefinitionModel]) -> SettingsResponse:
        by_category: dict[str, list[SettingItemSchema]] = {}
        for definition in definitions:
            by_category.setdefault(definition.category, []).append(
                self._to_item(definition)
            )

        categories: list[SettingCategorySchema] = []
        for cat in SETTING_CATEGORIES:
            slug = cat["slug"]
            items = by_category.get(slug, [])
            if items:
                categories.append(
                    SettingCategorySchema(
                        slug=slug,
                        label=cat["label"],
                        description=cat.get("description"),
                        settings=sorted(items, key=lambda s: s.sort_order),
                    )
                )

        total = sum(len(c.settings) for c in categories)
        return SettingsResponse(categories=categories, total=total)

    async def get_settings(
        self,
        category: str | None = None,
        search: str | None = None,
        *,
        use_cache: bool = True,
    ) -> SettingsResponse:
        cache_key = CACHE_KEY_ALL if not category else f"app_settings:category:{category}"
        if use_cache and not search:
            cached = await settings_cache.get(cache_key)
            if cached:
                return SettingsResponse(**cached)

        definitions = await self.repository.list_definitions(category=category)
        response = self._build_response(definitions)

        if search:
            query = search.lower()
            filtered: list[SettingCategorySchema] = []
            for cat in response.categories:
                settings = [
                    s
                    for s in cat.settings
                    if query in s.label.lower()
                    or query in s.key.lower()
                    or (s.description and query in s.description.lower())
                ]
                if settings:
                    filtered.append(
                        SettingCategorySchema(
                            slug=cat.slug,
                            label=cat.label,
                            description=cat.description,
                            settings=settings,
                        )
                    )
            response = SettingsResponse(
                categories=filtered,
                total=sum(len(c.settings) for c in filtered),
            )
        elif use_cache:
            await settings_cache.set(cache_key, response.model_dump())

        return response

    async def update_settings(
        self,
        updates: list[dict[str, Any]],
        user_id: str | None = None,
    ) -> SettingsUpdateResponse:
        updated_items: list[SettingItemSchema] = []

        for item in updates:
            category = item["category"]
            key = item["key"]
            value = item["value"]

            definition = await self.repository.get_definition(category, key)
            if not definition:
                raise NotFoundError("Setting", f"{category}.{key}")
            if not definition.is_editable:
                raise ValidationError(f"Setting {category}.{key} is not editable")

            validation = parse_json_field(definition.validation_json)
            options = parse_json_field(definition.options_json)
            normalized = validate_setting_value(
                definition.value_type,
                value,
                validation if isinstance(validation, dict) else None,
                options if isinstance(options, list) else None,
            )

            default = self.repository.deserialize(definition.default_value)
            if normalized == default:
                await self.repository.delete_value(definition.id)
            else:
                await self.repository.upsert_value(definition.id, normalized, user_id)

            refreshed = await self.repository.get_definition(category, key)
            if refreshed:
                updated_items.append(self._to_item(refreshed))

        await settings_cache.invalidate_all()
        try:
            from app.features.activity.emit import emit_activity

            await emit_activity(
                user_id=user_id,
                action="SETTINGS_UPDATED",
                message=f"Updated {len(updated_items)} setting(s)",
                status="info",
                metadata={"count": len(updated_items)},
            )
        except Exception:
            pass
        return SettingsUpdateResponse(updated=len(updated_items), settings=updated_items)

    async def reset_category(self, category: str, *, user_id: str | None = None) -> int:
        if category not in self.CATEGORY_LABELS:
            raise NotFoundError("SettingCategory", category)
        count = await self.repository.reset_category(category)
        await settings_cache.invalidate_all()
        try:
            from app.features.activity.emit import emit_activity

            await emit_activity(
                user_id=user_id,
                action="SETTINGS_RESET",
                message=f"Reset settings category '{category}' ({count} value(s))",
                status="info",
                metadata={"category": category, "reset_count": count},
            )
        except Exception:
            pass
        return count

    async def export_settings(self) -> SettingsExportResponse:
        response = await self.get_settings(use_cache=True)
        flat: dict[str, Any] = {}
        for cat in response.categories:
            for setting in cat.settings:
                flat[f"{cat.slug}.{setting.key}"] = setting.value
        return SettingsExportResponse(
            exported_at=datetime.now(UTC).isoformat(),
            settings=flat,
        )

    async def import_settings(
        self,
        payload: dict[str, Any],
        *,
        merge: bool = True,
        user_id: str | None = None,
    ) -> SettingsImportResponse:
        imported = 0
        skipped = 0
        errors: list[str] = []

        for compound_key, value in payload.items():
            parts = compound_key.split(".", 1)
            if len(parts) != 2:
                errors.append(f"Invalid key format: {compound_key}")
                skipped += 1
                continue

            category, key = parts
            definition = await self.repository.get_definition(category, key)
            if not definition:
                errors.append(f"Unknown setting: {compound_key}")
                skipped += 1
                continue

            try:
                validation = parse_json_field(definition.validation_json)
                options = parse_json_field(definition.options_json)
                normalized = validate_setting_value(
                    definition.value_type,
                    value,
                    validation if isinstance(validation, dict) else None,
                    options if isinstance(options, list) else None,
                )
                default = self.repository.deserialize(definition.default_value)
                if normalized == default:
                    if not merge:
                        await self.repository.delete_value(definition.id)
                else:
                    await self.repository.upsert_value(
                        definition.id, normalized, user_id
                    )
                imported += 1
            except ValidationError as e:
                errors.append(f"{compound_key}: {e.message}")
                skipped += 1

        await settings_cache.invalidate_all()
        try:
            from app.features.activity.emit import emit_activity

            await emit_activity(
                user_id=user_id,
                action="SETTINGS_IMPORTED",
                message=f"Imported {imported} setting(s)",
                status="info",
                metadata={"imported": imported, "skipped": skipped},
            )
        except Exception:
            pass
        return SettingsImportResponse(imported=imported, skipped=skipped, errors=errors)

    async def get_value(self, category: str, key: str, *, default: Any = None) -> Any:
        """Read a single effective setting (for use by other services)."""
        definition = await self.repository.get_definition(category, key)
        if not definition:
            return default
        value, _ = self._effective_value(definition)
        return value

    async def get_display_settings(self) -> DisplaySettingsResponse:
        """Resolved general + notification values for any signed-in user."""
        response = await self.get_settings(use_cache=True)
        flat: dict[str, Any] = {}
        for cat in response.categories:
            if cat.slug not in {"general", "notifications"}:
                continue
            for setting in cat.settings:
                flat[setting.key] = setting.value
        defaults = DisplaySettingsResponse()
        return DisplaySettingsResponse(
            **{
                field: flat.get(field, getattr(defaults, field))
                for field in DisplaySettingsResponse.model_fields
            }
        )
