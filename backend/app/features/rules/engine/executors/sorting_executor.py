"""Sorting rules executor."""

from typing import Any

from app.features.rules.engine.context import Dataset, ExecutionContext
from app.features.rules.engine.executors.base import BaseRuleExecutor
from app.infrastructure.database.models import ConfigurableRuleModel


class SortingRuleExecutor(BaseRuleExecutor):
    """Executor for sorting rules."""

    async def execute(
        self,
        dataset: Dataset,
        rule: ConfigurableRuleModel,
        context: ExecutionContext,
    ) -> Dataset:
        """Execute sorting rule."""
        config = self.get_config(rule)
        rule_type = rule.rule_type

        if rule_type == "single":
            return self._single_sort(dataset, config, context)
        elif rule_type == "multi":
            return self._multi_sort(dataset, config, context)
        elif rule_type == "custom":
            return self._custom_sort(dataset, config, context)

        return dataset

    def _single_sort(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Sort by a single column."""
        column = config.get("column", "")
        direction = config.get("direction", "asc")

        if column not in dataset.columns:
            context.add_warning(f"Column '{column}' not found for sorting")
            return dataset

        reverse = direction.lower() == "desc"

        sorted_rows = sorted(
            dataset.rows,
            key=lambda row: self._sort_key(row.get(column)),
            reverse=reverse,
        )

        return Dataset(columns=dataset.columns, rows=sorted_rows, name=dataset.name)

    def _multi_sort(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Sort by multiple columns with priority."""
        sorts = config.get("sorts", [])

        if not sorts:
            return dataset

        sorts_ordered = sorted(sorts, key=lambda s: s.get("priority", 1))

        def multi_sort_key(row: dict) -> tuple:
            keys = []
            for sort in sorts_ordered:
                column = sort.get("column", "")
                direction = sort.get("direction", "asc")
                value = row.get(column)
                key = self._sort_key(value)
                if direction.lower() == "desc":
                    key = self._reverse_key(key)
                keys.append(key)
            return tuple(keys)

        sorted_rows = sorted(dataset.rows, key=multi_sort_key)

        return Dataset(columns=dataset.columns, rows=sorted_rows, name=dataset.name)

    def _custom_sort(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Sort using a custom expression."""
        from app.features.rules.expressions.evaluator import ExpressionEvaluator

        expression = config.get("expression", "")

        if not expression:
            return dataset

        evaluator = ExpressionEvaluator()

        def custom_key(row: dict) -> Any:
            try:
                value = evaluator.evaluate(expression, row, context.variables)
                return self._sort_key(value)
            except Exception:
                return self._sort_key(None)

        sorted_rows = sorted(dataset.rows, key=custom_key)

        return Dataset(columns=dataset.columns, rows=sorted_rows, name=dataset.name)

    @staticmethod
    def _sort_key(value: Any) -> tuple:
        """Create a sortable key handling nulls and mixed types."""
        if value is None:
            return (1, "")
        try:
            return (0, float(value))
        except (ValueError, TypeError):
            return (0, str(value))

    @staticmethod
    def _reverse_key(key: tuple) -> tuple:
        """Create a reversed sort key."""
        is_null, value = key
        if isinstance(value, (int, float)):
            return (is_null, -value)
        else:
            return (is_null, "".join(chr(255 - ord(c)) if ord(c) < 256 else c for c in str(value)))
