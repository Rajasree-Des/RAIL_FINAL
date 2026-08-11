"""Column rules executor."""

from app.features.rules.engine.context import Dataset, ExecutionContext
from app.features.rules.engine.executors.base import BaseRuleExecutor
from app.infrastructure.database.models import ConfigurableRuleModel


class ColumnRuleExecutor(BaseRuleExecutor):
    """Executor for column manipulation rules."""

    async def execute(
        self,
        dataset: Dataset,
        rule: ConfigurableRuleModel,
        context: ExecutionContext,
    ) -> Dataset:
        """Execute column rule."""
        config = self.get_config(rule)
        rule_type = rule.rule_type

        if rule_type == "rename":
            return self._rename_column(dataset, config, context)
        elif rule_type == "hide":
            return self._hide_columns(dataset, config, context)
        elif rule_type == "create":
            return self._create_column(dataset, config, context)
        elif rule_type == "delete":
            return self._delete_columns(dataset, config, context)
        elif rule_type == "reorder":
            return self._reorder_columns(dataset, config, context)
        elif rule_type == "copy":
            return self._copy_column(dataset, config, context)

        return dataset

    def _rename_column(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Rename a column."""
        source = config.get("source", "")
        target = config.get("target", "")

        if source not in dataset.columns:
            context.add_warning(f"Column '{source}' not found for rename")
            return dataset

        new_columns = [target if c == source else c for c in dataset.columns]
        new_rows = []
        for row in dataset.rows:
            new_row = {}
            for key, value in row.items():
                if key == source:
                    new_row[target] = value
                else:
                    new_row[key] = value
            new_rows.append(new_row)

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    def _hide_columns(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Hide (remove) columns from output."""
        columns_to_hide = config.get("columns", [])

        new_columns = [c for c in dataset.columns if c not in columns_to_hide]
        new_rows = []
        for row in dataset.rows:
            new_row = {k: v for k, v in row.items() if k not in columns_to_hide}
            new_rows.append(new_row)

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    def _create_column(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Create a computed column."""
        from app.features.rules.expressions.evaluator import ExpressionEvaluator

        name = config.get("name", "")
        expression = config.get("expression", "")

        evaluator = ExpressionEvaluator()

        new_columns = dataset.columns + [name] if name not in dataset.columns else dataset.columns
        new_rows = []

        for i, row in enumerate(dataset.rows):
            new_row = row.copy()
            try:
                value = evaluator.evaluate(expression, row, context.variables)
                new_row[name] = value
            except Exception as e:
                context.add_error(f"Error evaluating expression: {e}", row_index=i)
                new_row[name] = None
            new_rows.append(new_row)

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    def _delete_columns(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Delete columns from dataset."""
        columns_to_delete = config.get("columns", [])
        return self._hide_columns(dataset, {"columns": columns_to_delete}, context)

    def _reorder_columns(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Reorder columns."""
        order = config.get("order", [])

        new_columns = []
        for col in order:
            if col in dataset.columns:
                new_columns.append(col)

        for col in dataset.columns:
            if col not in new_columns:
                new_columns.append(col)

        new_rows = []
        for row in dataset.rows:
            new_row = {col: row.get(col) for col in new_columns}
            new_rows.append(new_row)

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    def _copy_column(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Copy a column."""
        source = config.get("source", "")
        target = config.get("target", "")

        if source not in dataset.columns:
            context.add_warning(f"Column '{source}' not found for copy")
            return dataset

        new_columns = dataset.columns + [target] if target not in dataset.columns else dataset.columns
        new_rows = []
        for row in dataset.rows:
            new_row = row.copy()
            new_row[target] = row.get(source)
            new_rows.append(new_row)

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)
