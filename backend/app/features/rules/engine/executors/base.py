"""Base executor interface for all rule types."""

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from app.features.rules.engine.context import Dataset, ExecutionContext
from app.infrastructure.database.models import ConfigurableRuleModel


class BaseRuleExecutor(ABC):
    """Abstract base class for rule executors."""

    @abstractmethod
    async def execute(
        self,
        dataset: Dataset,
        rule: ConfigurableRuleModel,
        context: ExecutionContext,
    ) -> Dataset:
        """Execute the rule and return the modified dataset."""
        pass

    def get_config(self, rule: ConfigurableRuleModel) -> dict[str, Any]:
        """Parse and return rule configuration."""
        if rule.config_json:
            return json.loads(rule.config_json)
        return {}

    def get_conditions(self, rule: ConfigurableRuleModel) -> dict[str, Any] | None:
        """Parse and return rule conditions."""
        if rule.conditions_json:
            return json.loads(rule.conditions_json)
        return None

    def evaluate_condition(
        self,
        condition: dict[str, Any],
        row: dict[str, Any],
    ) -> bool:
        """Evaluate a single condition against a row."""
        field = condition.get("field", "")
        operator = condition.get("operator", "equals")
        value = condition.get("value")

        row_value = row.get(field)

        if operator == "equals":
            return row_value == value
        elif operator == "not_equals":
            return row_value != value
        elif operator == "contains":
            return value in str(row_value) if row_value is not None else False
        elif operator == "not_contains":
            return value not in str(row_value) if row_value is not None else True
        elif operator == "starts_with":
            return str(row_value).startswith(value) if row_value is not None else False
        elif operator == "ends_with":
            return str(row_value).endswith(value) if row_value is not None else False
        elif operator == "gt":
            return self._compare_values(row_value, value) > 0
        elif operator == "lt":
            return self._compare_values(row_value, value) < 0
        elif operator == "gte":
            return self._compare_values(row_value, value) >= 0
        elif operator == "lte":
            return self._compare_values(row_value, value) <= 0
        elif operator == "in":
            return row_value in (value if isinstance(value, list) else [value])
        elif operator == "not_in":
            return row_value not in (value if isinstance(value, list) else [value])
        elif operator == "is_null":
            return row_value is None or row_value == ""
        elif operator == "is_not_null":
            return row_value is not None and row_value != ""
        elif operator == "between":
            if isinstance(value, list) and len(value) == 2:
                return self._compare_values(row_value, value[0]) >= 0 and \
                       self._compare_values(row_value, value[1]) <= 0
            return False
        elif operator == "regex":
            try:
                return bool(re.match(value, str(row_value))) if row_value is not None else False
            except re.error:
                return False

        return False

    def evaluate_condition_group(
        self,
        group: dict[str, Any],
        row: dict[str, Any],
    ) -> bool:
        """Evaluate a condition group with logic operator."""
        logic = group.get("logic", "AND")
        conditions = group.get("conditions", [])
        nested = group.get("nested", [])

        results = []

        for condition in conditions:
            results.append(self.evaluate_condition(condition, row))

        for nested_group in nested:
            results.append(self.evaluate_condition_group(nested_group, row))

        if not results:
            return True

        if logic == "AND":
            return all(results)
        else:
            return any(results)

    def _compare_values(self, a: Any, b: Any) -> int:
        """Compare two values, handling different types."""
        if a is None and b is None:
            return 0
        if a is None:
            return -1
        if b is None:
            return 1

        try:
            a_num = float(a)
            b_num = float(b)
            if a_num < b_num:
                return -1
            elif a_num > b_num:
                return 1
            return 0
        except (ValueError, TypeError):
            a_str = str(a)
            b_str = str(b)
            if a_str < b_str:
                return -1
            elif a_str > b_str:
                return 1
            return 0

    def should_apply_to_row(
        self,
        rule: ConfigurableRuleModel,
        row: dict[str, Any],
    ) -> bool:
        """Check if rule should apply to a specific row based on conditions."""
        conditions = self.get_conditions(rule)
        if not conditions:
            return True
        return self.evaluate_condition_group(conditions, row)
