"""Filter rules executor."""

from app.features.rules.engine.context import Dataset, ExecutionContext
from app.features.rules.engine.executors.base import BaseRuleExecutor
from app.infrastructure.database.models import ConfigurableRuleModel


class FilterRuleExecutor(BaseRuleExecutor):
    """Executor for filter rules."""

    async def execute(
        self,
        dataset: Dataset,
        rule: ConfigurableRuleModel,
        context: ExecutionContext,
    ) -> Dataset:
        """Execute filter rule."""
        config = self.get_config(rule)
        rule_type = rule.rule_type

        if rule_type == "include":
            return self._include_filter(dataset, config, context)
        elif rule_type == "exclude":
            return self._exclude_filter(dataset, config, context)
        elif rule_type == "distinct":
            return self._distinct_filter(dataset, config, context)
        elif rule_type == "not_null":
            return self._not_null_filter(dataset, config, context)

        return dataset

    def _include_filter(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Keep only rows matching conditions."""
        logic = config.get("logic", "AND")
        conditions = config.get("conditions", [])

        condition_group = {"logic": logic, "conditions": conditions}

        new_rows = [
            row for row in dataset.rows
            if self.evaluate_condition_group(condition_group, row)
        ]

        return Dataset(columns=dataset.columns, rows=new_rows, name=dataset.name)

    def _exclude_filter(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Remove rows matching conditions."""
        logic = config.get("logic", "AND")
        conditions = config.get("conditions", [])

        condition_group = {"logic": logic, "conditions": conditions}

        new_rows = [
            row for row in dataset.rows
            if not self.evaluate_condition_group(condition_group, row)
        ]

        return Dataset(columns=dataset.columns, rows=new_rows, name=dataset.name)

    def _distinct_filter(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Keep only distinct rows based on specified columns."""
        columns = config.get("columns", [])

        if not columns:
            columns = dataset.columns

        seen = set()
        new_rows = []

        for row in dataset.rows:
            key = tuple(row.get(col) for col in columns)
            if key not in seen:
                seen.add(key)
                new_rows.append(row)

        return Dataset(columns=dataset.columns, rows=new_rows, name=dataset.name)

    def _not_null_filter(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Keep rows where specified columns are not null."""
        columns = config.get("columns", [])

        def has_all_values(row: dict) -> bool:
            for col in columns:
                value = row.get(col)
                if value is None or value == "":
                    return False
            return True

        new_rows = [row for row in dataset.rows if has_all_values(row)]

        return Dataset(columns=dataset.columns, rows=new_rows, name=dataset.name)
