"""Conditional rules executor."""

from app.features.rules.engine.context import Dataset, ExecutionContext
from app.features.rules.engine.executors.base import BaseRuleExecutor
from app.infrastructure.database.models import ConfigurableRuleModel


class ConditionalRuleExecutor(BaseRuleExecutor):
    """Executor for conditional rules."""

    async def execute(
        self,
        dataset: Dataset,
        rule: ConfigurableRuleModel,
        context: ExecutionContext,
    ) -> Dataset:
        """Execute conditional rule."""
        config = self.get_config(rule)
        rule_type = rule.rule_type

        if rule_type == "include_column":
            return self._include_column(dataset, config, context)
        elif rule_type == "exclude_column":
            return self._exclude_column(dataset, config, context)
        elif rule_type == "set_value":
            return self._set_value(dataset, config, context)
        elif rule_type == "apply_format":
            return self._apply_format(dataset, config, context)

        return dataset

    def _include_column(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Include a column only if condition is met for any row."""
        condition = config.get("condition", {})
        column = config.get("column", "")

        should_include = False
        for row in dataset.rows:
            if self.evaluate_condition_group(condition, row):
                should_include = True
                break

        if not should_include and column in dataset.columns:
            new_columns = [c for c in dataset.columns if c != column]
            new_rows = [{k: v for k, v in row.items() if k != column} for row in dataset.rows]
            return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

        return dataset

    def _exclude_column(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Exclude a column if condition is met for any row."""
        condition = config.get("condition", {})
        column = config.get("column", "")

        should_exclude = False
        for row in dataset.rows:
            if self.evaluate_condition_group(condition, row):
                should_exclude = True
                break

        if should_exclude and column in dataset.columns:
            new_columns = [c for c in dataset.columns if c != column]
            new_rows = [{k: v for k, v in row.items() if k != column} for row in dataset.rows]
            return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

        return dataset

    def _set_value(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Set cell values when condition is met."""
        condition = config.get("condition", {})
        column = config.get("column", "")
        value = config.get("value")

        new_rows = []
        for row in dataset.rows:
            new_row = row.copy()
            if self.evaluate_condition_group(condition, row):
                new_row[column] = value
            new_rows.append(new_row)

        new_columns = dataset.columns
        if column not in new_columns:
            new_columns = new_columns + [column]

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    def _apply_format(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Apply formatting when condition is met (stored as metadata)."""
        condition = config.get("condition", {})
        column = config.get("column", "")
        format_str = config.get("format", "")

        for i, row in enumerate(dataset.rows):
            if self.evaluate_condition_group(condition, row):
                context.set_variable(f"_format_{i}_{column}", format_str)

        return dataset
