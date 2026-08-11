"""Top/Limit rules executor."""

from app.features.rules.engine.context import Dataset, ExecutionContext
from app.features.rules.engine.executors.base import BaseRuleExecutor
from app.infrastructure.database.models import ConfigurableRuleModel


class TopRuleExecutor(BaseRuleExecutor):
    """Executor for top/limit rules."""

    async def execute(
        self,
        dataset: Dataset,
        rule: ConfigurableRuleModel,
        context: ExecutionContext,
    ) -> Dataset:
        """Execute top/limit rule."""
        config = self.get_config(rule)
        rule_type = rule.rule_type

        if rule_type == "top_n":
            return self._top_n(dataset, config, context)
        elif rule_type == "bottom_n":
            return self._bottom_n(dataset, config, context)
        elif rule_type == "percent":
            return self._top_percent(dataset, config, context)
        elif rule_type == "limit":
            return self._limit(dataset, config, context)

        return dataset

    def _top_n(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Get top N rows by column value."""
        n = config.get("n", 10)
        by_column = config.get("by_column", "")
        direction = config.get("direction", "desc")

        if by_column not in dataset.columns:
            context.add_warning(f"Column '{by_column}' not found for top_n")
            return dataset

        reverse = direction.lower() == "desc"

        sorted_rows = sorted(
            dataset.rows,
            key=lambda row: self._sort_key(row.get(by_column)),
            reverse=reverse,
        )

        return Dataset(
            columns=dataset.columns,
            rows=sorted_rows[:n],
            name=dataset.name,
        )

    def _bottom_n(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Get bottom N rows by column value."""
        n = config.get("n", 10)
        by_column = config.get("by_column", "")
        direction = config.get("direction", "asc")

        if by_column not in dataset.columns:
            context.add_warning(f"Column '{by_column}' not found for bottom_n")
            return dataset

        reverse = direction.lower() == "desc"

        sorted_rows = sorted(
            dataset.rows,
            key=lambda row: self._sort_key(row.get(by_column)),
            reverse=reverse,
        )

        return Dataset(
            columns=dataset.columns,
            rows=sorted_rows[:n],
            name=dataset.name,
        )

    def _top_percent(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Get top percentage of rows."""
        percent = config.get("percent", 10)
        by_column = config.get("by_column", "")
        direction = config.get("direction", "desc")

        if by_column not in dataset.columns:
            context.add_warning(f"Column '{by_column}' not found for top_percent")
            return dataset

        n = max(1, int(len(dataset.rows) * percent / 100))

        return self._top_n(
            dataset,
            {"n": n, "by_column": by_column, "direction": direction},
            context,
        )

    def _limit(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Apply limit and offset."""
        offset = config.get("offset", 0)
        limit = config.get("limit", len(dataset.rows))

        new_rows = dataset.rows[offset : offset + limit]

        return Dataset(columns=dataset.columns, rows=new_rows, name=dataset.name)

    @staticmethod
    def _sort_key(value):
        """Create a sortable key handling nulls and mixed types."""
        if value is None:
            return (1, 0)
        try:
            return (0, float(value))
        except (ValueError, TypeError):
            return (0, str(value))
