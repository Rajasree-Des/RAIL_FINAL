"""Calculation rules executor."""

from collections import defaultdict
from statistics import mean, median, stdev, variance
from typing import Any

from app.features.rules.engine.context import Dataset, ExecutionContext
from app.features.rules.engine.executors.base import BaseRuleExecutor
from app.infrastructure.database.models import ConfigurableRuleModel


class CalculationRuleExecutor(BaseRuleExecutor):
    """Executor for calculation rules."""

    async def execute(
        self,
        dataset: Dataset,
        rule: ConfigurableRuleModel,
        context: ExecutionContext,
    ) -> Dataset:
        """Execute calculation rule."""
        config = self.get_config(rule)
        rule_type = rule.rule_type

        if rule_type == "percentage":
            return self._percentage(dataset, config, context)
        elif rule_type == "aggregate":
            return self._aggregate(dataset, config, context)
        elif rule_type == "expression":
            return self._expression(dataset, config, context)
        elif rule_type == "running":
            return self._running(dataset, config, context)
        elif rule_type == "difference":
            return self._difference(dataset, config, context)
        elif rule_type == "trend":
            return self._trend(dataset, config, context)

        return dataset

    def _percentage(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Calculate percentage from two columns."""
        numerator = config.get("numerator", "")
        denominator = config.get("denominator", "")
        target = config.get("target", "")
        decimal_places = config.get("decimal_places", 2)

        new_columns = dataset.columns
        if target not in new_columns:
            new_columns = new_columns + [target]

        new_rows = []
        for i, row in enumerate(dataset.rows):
            new_row = row.copy()
            try:
                num = float(row.get(numerator, 0) or 0)
                den = float(row.get(denominator, 0) or 0)
                if den != 0:
                    value = round((num / den) * 100, decimal_places)
                else:
                    value = 0
                new_row[target] = value
            except (ValueError, TypeError) as e:
                context.add_error(f"Error calculating percentage: {e}", row_index=i)
                new_row[target] = None
            new_rows.append(new_row)

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    def _aggregate(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Calculate aggregate values, optionally grouped."""
        function = config.get("function", "sum")
        column = config.get("column", "")
        group_by = config.get("group_by", [])
        target = config.get("target", "")

        if not group_by:
            values = self._extract_numeric_values(dataset.rows, column)
            result = self._compute_aggregate(function, values)

            new_columns = dataset.columns
            if target not in new_columns:
                new_columns = new_columns + [target]

            new_rows = []
            for row in dataset.rows:
                new_row = row.copy()
                new_row[target] = result
                new_rows.append(new_row)

            return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)
        else:
            groups: dict[tuple, list[dict]] = defaultdict(list)
            for row in dataset.rows:
                key = tuple(row.get(col) for col in group_by)
                groups[key].append(row)

            group_results: dict[tuple, Any] = {}
            for key, rows in groups.items():
                values = self._extract_numeric_values(rows, column)
                group_results[key] = self._compute_aggregate(function, values)

            new_columns = dataset.columns
            if target not in new_columns:
                new_columns = new_columns + [target]

            new_rows = []
            for row in dataset.rows:
                new_row = row.copy()
                key = tuple(row.get(col) for col in group_by)
                new_row[target] = group_results.get(key)
                new_rows.append(new_row)

            return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    def _expression(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Calculate using custom expression."""
        from app.features.rules.expressions.evaluator import ExpressionEvaluator

        expression = config.get("expression", "")
        target = config.get("target", "")

        evaluator = ExpressionEvaluator()

        new_columns = dataset.columns
        if target not in new_columns:
            new_columns = new_columns + [target]

        new_rows = []
        for i, row in enumerate(dataset.rows):
            new_row = row.copy()
            try:
                value = evaluator.evaluate(expression, row, context.variables)
                new_row[target] = value
            except Exception as e:
                context.add_error(f"Expression error: {e}", row_index=i)
                new_row[target] = None
            new_rows.append(new_row)

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    def _running(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Calculate running totals/averages."""
        function = config.get("function", "sum")
        column = config.get("column", "")
        order_by = config.get("order_by", "")
        target = config.get("target", "")

        sorted_rows = sorted(
            enumerate(dataset.rows),
            key=lambda x: self._sort_key(x[1].get(order_by)),
        )

        running_values: list[float] = []
        results: dict[int, Any] = {}

        for original_index, row in sorted_rows:
            try:
                value = float(row.get(column, 0) or 0)
            except (ValueError, TypeError):
                value = 0

            running_values.append(value)
            results[original_index] = self._compute_aggregate(function, running_values)

        new_columns = dataset.columns
        if target not in new_columns:
            new_columns = new_columns + [target]

        new_rows = []
        for i, row in enumerate(dataset.rows):
            new_row = row.copy()
            new_row[target] = results.get(i)
            new_rows.append(new_row)

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    def _difference(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Calculate difference between columns."""
        column1 = config.get("column1", "")
        column2 = config.get("column2", "")
        target = config.get("target", "")

        new_columns = dataset.columns
        if target not in new_columns:
            new_columns = new_columns + [target]

        new_rows = []
        for i, row in enumerate(dataset.rows):
            new_row = row.copy()
            try:
                val1 = float(row.get(column1, 0) or 0)
                val2 = float(row.get(column2, 0) or 0)
                new_row[target] = val1 - val2
            except (ValueError, TypeError) as e:
                context.add_error(f"Error calculating difference: {e}", row_index=i)
                new_row[target] = None
            new_rows.append(new_row)

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    def _trend(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Calculate trend over periods."""
        column = config.get("column", "")
        periods = config.get("periods", 1)
        target = config.get("target", "")

        new_columns = dataset.columns
        if target not in new_columns:
            new_columns = new_columns + [target]

        new_rows = []
        for i, row in enumerate(dataset.rows):
            new_row = row.copy()
            if i < periods:
                new_row[target] = None
            else:
                try:
                    current = float(row.get(column, 0) or 0)
                    previous = float(dataset.rows[i - periods].get(column, 0) or 0)
                    if previous != 0:
                        trend = ((current - previous) / previous) * 100
                    else:
                        trend = 0 if current == 0 else 100
                    new_row[target] = round(trend, 2)
                except (ValueError, TypeError):
                    new_row[target] = None
            new_rows.append(new_row)

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    @staticmethod
    def _extract_numeric_values(rows: list[dict], column: str) -> list[float]:
        """Extract numeric values from a column."""
        values = []
        for row in rows:
            try:
                values.append(float(row.get(column, 0) or 0))
            except (ValueError, TypeError):
                pass
        return values

    @staticmethod
    def _compute_aggregate(function: str, values: list[float]) -> Any:
        """Compute aggregate function on values."""
        if not values:
            return 0

        if function == "sum":
            return sum(values)
        elif function == "avg":
            return mean(values)
        elif function == "count":
            return len(values)
        elif function == "min":
            return min(values)
        elif function == "max":
            return max(values)
        elif function == "median":
            return median(values)
        elif function == "stddev":
            return stdev(values) if len(values) > 1 else 0
        elif function == "variance":
            return variance(values) if len(values) > 1 else 0

        return 0

    @staticmethod
    def _sort_key(value):
        """Create a sortable key."""
        if value is None:
            return (1, "")
        try:
            return (0, float(value))
        except (ValueError, TypeError):
            return (0, str(value))
