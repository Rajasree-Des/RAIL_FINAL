"""Service layer for Business Rules Engine."""

import json
from typing import Any

from app.core.exceptions import NotFoundError, ValidationError
from app.features.rules.repository import RuleRepository
from app.features.rules.schemas import (
    CategoryInfo,
    FunctionInfo,
    RuleListItem,
    RuleResponse,
    RuleTypeInfo,
    RuleValidationResult,
)
from app.infrastructure.database.models import ConfigurableRuleModel


RULE_CATEGORIES = {
    "column": {
        "name": "Column Rules",
        "description": "Modify dataset structure: rename, hide, create, delete, reorder columns",
        "types": {
            "rename": {
                "name": "Rename Column",
                "description": "Rename a column to a new name",
                "required_fields": ["source", "target"],
            },
            "hide": {
                "name": "Hide Columns",
                "description": "Hide columns from output",
                "required_fields": ["columns"],
            },
            "create": {
                "name": "Create Column",
                "description": "Create a computed column using an expression",
                "required_fields": ["name", "expression"],
            },
            "delete": {
                "name": "Delete Columns",
                "description": "Remove columns from dataset",
                "required_fields": ["columns"],
            },
            "reorder": {
                "name": "Reorder Columns",
                "description": "Set the display order of columns",
                "required_fields": ["order"],
            },
            "copy": {
                "name": "Copy Column",
                "description": "Create a copy of an existing column",
                "required_fields": ["source", "target"],
            },
        },
    },
    "conditional": {
        "name": "Conditional Rules",
        "description": "Apply actions based on conditions",
        "types": {
            "include_column": {
                "name": "Include Column If",
                "description": "Include a column only when condition is met",
                "required_fields": ["condition", "column"],
            },
            "exclude_column": {
                "name": "Exclude Column If",
                "description": "Exclude a column when condition is met",
                "required_fields": ["condition", "column"],
            },
            "set_value": {
                "name": "Set Value If",
                "description": "Set a cell value when condition is met",
                "required_fields": ["condition", "column", "value"],
            },
            "apply_format": {
                "name": "Apply Format If",
                "description": "Apply formatting when condition is met",
                "required_fields": ["condition", "column", "format"],
            },
        },
    },
    "sorting": {
        "name": "Sorting Rules",
        "description": "Define how data is sorted",
        "types": {
            "single": {
                "name": "Single Column Sort",
                "description": "Sort by a single column",
                "required_fields": ["column", "direction"],
            },
            "multi": {
                "name": "Multi-Column Sort",
                "description": "Sort by multiple columns with priority",
                "required_fields": ["sorts"],
            },
            "custom": {
                "name": "Custom Sort",
                "description": "Sort using a custom expression",
                "required_fields": ["expression"],
            },
        },
    },
    "filter": {
        "name": "Filter Rules",
        "description": "Filter rows based on conditions",
        "types": {
            "include": {
                "name": "Include Rows",
                "description": "Include rows matching conditions",
                "required_fields": ["conditions"],
            },
            "exclude": {
                "name": "Exclude Rows",
                "description": "Exclude rows matching conditions",
                "required_fields": ["conditions"],
            },
            "distinct": {
                "name": "Distinct Rows",
                "description": "Keep only distinct rows by columns",
                "required_fields": ["columns"],
            },
            "not_null": {
                "name": "Not Null Filter",
                "description": "Filter out rows with null values",
                "required_fields": ["columns"],
            },
        },
    },
    "top": {
        "name": "Top/Limit Rules",
        "description": "Limit output to top/bottom N rows",
        "types": {
            "top_n": {
                "name": "Top N",
                "description": "Get top N rows by column value",
                "required_fields": ["n", "by_column"],
            },
            "bottom_n": {
                "name": "Bottom N",
                "description": "Get bottom N rows by column value",
                "required_fields": ["n", "by_column"],
            },
            "percent": {
                "name": "Top Percent",
                "description": "Get top percentage of rows",
                "required_fields": ["percent", "by_column"],
            },
            "limit": {
                "name": "Limit/Offset",
                "description": "Limit rows with offset",
                "required_fields": ["limit"],
            },
        },
    },
    "highlight": {
        "name": "Highlight Rules",
        "description": "Apply conditional formatting",
        "types": {
            "cell": {
                "name": "Highlight Cell",
                "description": "Highlight cells matching condition",
                "required_fields": ["condition", "style"],
            },
            "row": {
                "name": "Highlight Row",
                "description": "Highlight entire rows matching condition",
                "required_fields": ["condition", "style"],
            },
            "column": {
                "name": "Highlight Column",
                "description": "Highlight an entire column",
                "required_fields": ["column", "style"],
            },
            "gradient": {
                "name": "Gradient",
                "description": "Apply color gradient based on values",
                "required_fields": ["column", "min_color", "max_color"],
            },
            "data_bar": {
                "name": "Data Bar",
                "description": "Show data bars in cells",
                "required_fields": ["column", "color"],
            },
        },
    },
    "calculation": {
        "name": "Calculation Rules",
        "description": "Perform calculations on data",
        "types": {
            "percentage": {
                "name": "Percentage",
                "description": "Calculate percentage from two columns",
                "required_fields": ["numerator", "denominator", "target"],
            },
            "aggregate": {
                "name": "Aggregate",
                "description": "Calculate aggregate values",
                "required_fields": ["function", "column", "target"],
            },
            "expression": {
                "name": "Expression",
                "description": "Calculate using custom expression",
                "required_fields": ["expression", "target"],
            },
            "running": {
                "name": "Running Calculation",
                "description": "Calculate running totals/averages",
                "required_fields": ["function", "column", "order_by", "target"],
            },
            "difference": {
                "name": "Difference",
                "description": "Calculate difference between columns",
                "required_fields": ["column1", "column2", "target"],
            },
            "trend": {
                "name": "Trend",
                "description": "Calculate trend over periods",
                "required_fields": ["column", "periods", "target"],
            },
        },
    },
    "merge": {
        "name": "Merge Rules",
        "description": "Combine multiple datasets",
        "types": {
            "join": {
                "name": "Join",
                "description": "Join datasets on key columns",
                "required_fields": ["datasets", "on", "type"],
            },
            "union": {
                "name": "Union",
                "description": "Stack datasets vertically",
                "required_fields": ["datasets"],
            },
            "compare": {
                "name": "Compare",
                "description": "Compare two datasets",
                "required_fields": ["dataset1", "dataset2", "key_columns", "compare_columns"],
            },
            "dedupe": {
                "name": "Deduplicate",
                "description": "Remove duplicate rows",
                "required_fields": ["columns"],
            },
            "conflict": {
                "name": "Conflict Resolution",
                "description": "Define how to handle conflicts",
                "required_fields": ["strategy"],
            },
        },
    },
}


EXPRESSION_FUNCTIONS = [
    {
        "name": "sum",
        "description": "Sum of values",
        "signature": "sum(column)",
        "examples": ["sum(amount)", "sum(quantity)"],
    },
    {
        "name": "avg",
        "description": "Average of values",
        "signature": "avg(column)",
        "examples": ["avg(score)", "avg(rating)"],
    },
    {
        "name": "count",
        "description": "Count of values",
        "signature": "count(column) or count(*)",
        "examples": ["count(*)", "count(id)"],
    },
    {
        "name": "min",
        "description": "Minimum value",
        "signature": "min(column)",
        "examples": ["min(price)", "min(date)"],
    },
    {
        "name": "max",
        "description": "Maximum value",
        "signature": "max(column)",
        "examples": ["max(price)", "max(date)"],
    },
    {
        "name": "round",
        "description": "Round to decimal places",
        "signature": "round(value, decimals)",
        "examples": ["round(percentage, 2)", "round(amount, 0)"],
    },
    {
        "name": "abs",
        "description": "Absolute value",
        "signature": "abs(value)",
        "examples": ["abs(difference)", "abs(change)"],
    },
    {
        "name": "if",
        "description": "Conditional value",
        "signature": "if(condition, true_value, false_value)",
        "examples": ['if(status == "Active", 1, 0)', "if(amount > 100, amount * 0.9, amount)"],
    },
    {
        "name": "coalesce",
        "description": "First non-null value",
        "signature": "coalesce(value1, value2, ...)",
        "examples": ['coalesce(nickname, name, "Unknown")'],
    },
    {
        "name": "concat",
        "description": "Concatenate strings",
        "signature": "concat(value1, value2, ...)",
        "examples": ['concat(first_name, " ", last_name)'],
    },
    {
        "name": "upper",
        "description": "Convert to uppercase",
        "signature": "upper(value)",
        "examples": ["upper(name)", "upper(code)"],
    },
    {
        "name": "lower",
        "description": "Convert to lowercase",
        "signature": "lower(value)",
        "examples": ["lower(email)", "lower(status)"],
    },
    {
        "name": "trim",
        "description": "Remove whitespace",
        "signature": "trim(value)",
        "examples": ["trim(name)", "trim(address)"],
    },
    {
        "name": "date_diff",
        "description": "Difference between dates",
        "signature": "date_diff(date1, date2, unit)",
        "examples": ['date_diff(end_date, start_date, "days")'],
    },
]


class RuleService:
    """Service for managing business rules."""

    def __init__(self, repository: RuleRepository):
        self.repository = repository

    @staticmethod
    def _model_to_response(model: ConfigurableRuleModel) -> RuleResponse:
        """Convert model to response DTO."""
        return RuleResponse(
            id=model.id,
            name=model.name,
            description=model.description,
            template_id=model.template_id,
            category=model.category,
            rule_type=model.rule_type,
            config=json.loads(model.config_json) if model.config_json else {},
            priority=model.priority,
            group_id=model.group_id,
            is_enabled=model.is_enabled,
            is_global=model.is_global,
            conditions=json.loads(model.conditions_json) if model.conditions_json else None,
            is_deleted=model.is_deleted,
            created_by=model.created_by,
            updated_by=model.updated_by,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
        )

    @staticmethod
    def _model_to_list_item(model: ConfigurableRuleModel) -> RuleListItem:
        """Convert model to list item DTO."""
        return RuleListItem(
            id=model.id,
            name=model.name,
            description=model.description,
            template_id=model.template_id,
            category=model.category,
            rule_type=model.rule_type,
            priority=model.priority,
            group_id=model.group_id,
            is_enabled=model.is_enabled,
            is_global=model.is_global,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
        )

    async def list_rules(
        self,
        template_id: str | None = None,
        category: str | None = None,
        is_enabled: bool | None = None,
    ) -> list[RuleListItem]:
        """List rules with optional filters."""
        models = await self.repository.list_all(
            template_id=template_id,
            category=category,
            is_enabled=is_enabled,
        )
        return [self._model_to_list_item(m) for m in models]

    async def get_rule(self, rule_id: str) -> RuleResponse:
        """Get a rule by ID."""
        model = await self.repository.get_by_id(rule_id)
        if not model:
            raise NotFoundError("Rule", rule_id)
        return self._model_to_response(model)

    async def create_rule(
        self,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> RuleResponse:
        """Create a new rule."""
        validation = self.validate_rule_config(
            data.get("category", ""),
            data.get("rule_type", ""),
            data.get("config", {}),
        )
        if not validation.is_valid:
            raise ValidationError("; ".join(validation.errors))

        model = await self.repository.create(data, user_id)
        return self._model_to_response(model)

    async def update_rule(
        self,
        rule_id: str,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> RuleResponse:
        """Update a rule."""
        existing = await self.repository.get_by_id(rule_id)
        if not existing:
            raise NotFoundError("Rule", rule_id)

        category = data.get("category", existing.category)
        rule_type = data.get("rule_type", existing.rule_type)
        config = data.get("config")

        if config is not None:
            validation = self.validate_rule_config(category, rule_type, config)
            if not validation.is_valid:
                raise ValidationError("; ".join(validation.errors))

        model = await self.repository.update(rule_id, data, user_id)
        return self._model_to_response(model)

    async def delete_rule(
        self,
        rule_id: str,
        user_id: str | None = None,
    ) -> bool:
        """Delete a rule."""
        success = await self.repository.delete(rule_id, user_id)
        if not success:
            raise NotFoundError("Rule", rule_id)
        return True

    async def toggle_rule(
        self,
        rule_id: str,
        user_id: str | None = None,
    ) -> RuleResponse:
        """Toggle rule enabled status."""
        model = await self.repository.toggle_enabled(rule_id, user_id)
        if not model:
            raise NotFoundError("Rule", rule_id)
        return self._model_to_response(model)

    async def duplicate_rule(
        self,
        rule_id: str,
        new_name: str,
        user_id: str | None = None,
    ) -> RuleResponse:
        """Duplicate a rule."""
        model = await self.repository.duplicate(rule_id, new_name, user_id)
        if not model:
            raise NotFoundError("Rule", rule_id)
        return self._model_to_response(model)

    async def reorder_rules(
        self,
        rule_priorities: list[dict[str, Any]],
        user_id: str | None = None,
    ) -> int:
        """Update rule priorities."""
        return await self.repository.reorder(rule_priorities, user_id)

    def get_categories(self) -> list[CategoryInfo]:
        """Get available rule categories and types."""
        categories = []
        for cat_id, cat_info in RULE_CATEGORIES.items():
            types = []
            for type_id, type_info in cat_info["types"].items():
                types.append(
                    RuleTypeInfo(
                        type=type_id,
                        name=type_info["name"],
                        description=type_info["description"],
                        config_schema={"required_fields": type_info["required_fields"]},
                    )
                )
            categories.append(
                CategoryInfo(
                    category=cat_id,
                    name=cat_info["name"],
                    description=cat_info["description"],
                    rule_types=types,
                )
            )
        return categories

    def get_functions(self) -> list[FunctionInfo]:
        """Get available expression functions."""
        return [
            FunctionInfo(
                name=f["name"],
                description=f["description"],
                signature=f["signature"],
                examples=f["examples"],
            )
            for f in EXPRESSION_FUNCTIONS
        ]

    def validate_rule_config(
        self,
        category: str,
        rule_type: str,
        config: dict[str, Any],
    ) -> RuleValidationResult:
        """Validate a rule configuration."""
        errors: list[str] = []
        warnings: list[str] = []

        if category not in RULE_CATEGORIES:
            errors.append(f"Invalid category: {category}")
            return RuleValidationResult(is_valid=False, errors=errors)

        cat_info = RULE_CATEGORIES[category]
        if rule_type not in cat_info["types"]:
            errors.append(f"Invalid rule type '{rule_type}' for category '{category}'")
            return RuleValidationResult(is_valid=False, errors=errors)

        type_info = cat_info["types"][rule_type]
        required_fields = type_info.get("required_fields", [])

        for field in required_fields:
            if field not in config or config[field] is None:
                errors.append(f"Missing required field: {field}")
            elif isinstance(config[field], str) and not config[field].strip():
                errors.append(f"Field '{field}' cannot be empty")
            elif isinstance(config[field], list) and len(config[field]) == 0:
                errors.append(f"Field '{field}' cannot be empty")

        if category == "highlight" and "style" in config:
            style = config["style"]
            if isinstance(style, dict):
                if "background_color" in style:
                    color = style["background_color"]
                    if color and not self._is_valid_hex_color(color):
                        errors.append(f"Invalid color format: {color}")
                if "text_color" in style:
                    color = style["text_color"]
                    if color and not self._is_valid_hex_color(color):
                        errors.append(f"Invalid color format: {color}")

        if category == "top":
            if "n" in config:
                n = config["n"]
                if isinstance(n, int) and n <= 0:
                    errors.append("'n' must be a positive integer")
            if "percent" in config:
                pct = config["percent"]
                if isinstance(pct, (int, float)) and (pct <= 0 or pct > 100):
                    errors.append("'percent' must be between 0 and 100")

        if category == "sorting" and rule_type == "multi":
            if "sorts" in config and isinstance(config["sorts"], list):
                for i, sort in enumerate(config["sorts"]):
                    if not isinstance(sort, dict):
                        errors.append(f"Sort item {i} must be an object")
                    elif "column" not in sort:
                        errors.append(f"Sort item {i} missing 'column'")

        return RuleValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _is_valid_hex_color(color: str) -> bool:
        """Check if a string is a valid hex color."""
        if not color:
            return True
        if len(color) != 7 or not color.startswith("#"):
            return False
        try:
            int(color[1:], 16)
            return True
        except ValueError:
            return False
