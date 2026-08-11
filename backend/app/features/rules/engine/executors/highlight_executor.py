"""Highlight rules executor."""

from app.features.rules.engine.context import Dataset, ExecutionContext
from app.features.rules.engine.executors.base import BaseRuleExecutor
from app.infrastructure.database.models import ConfigurableRuleModel


class HighlightRuleExecutor(BaseRuleExecutor):
    """Executor for highlight rules."""

    async def execute(
        self,
        dataset: Dataset,
        rule: ConfigurableRuleModel,
        context: ExecutionContext,
    ) -> Dataset:
        """Execute highlight rule (adds to context, doesn't modify data)."""
        config = self.get_config(rule)
        rule_type = rule.rule_type

        if rule_type == "cell":
            self._highlight_cell(dataset, config, context)
        elif rule_type == "row":
            self._highlight_row(dataset, config, context)
        elif rule_type == "column":
            self._highlight_column(dataset, config, context)
        elif rule_type == "gradient":
            self._highlight_gradient(dataset, config, context)
        elif rule_type == "data_bar":
            self._highlight_data_bar(dataset, config, context)

        return dataset

    def _highlight_cell(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> None:
        """Highlight cells matching condition."""
        condition = config.get("condition", {})
        style = config.get("style", {})

        for i, row in enumerate(dataset.rows):
            if self.evaluate_condition_group(condition, row):
                field = condition.get("conditions", [{}])[0].get("field", "")
                if field:
                    context.add_highlight(
                        row_index=i,
                        column=field,
                        background_color=style.get("background_color"),
                        text_color=style.get("text_color"),
                        bold=style.get("bold", False),
                    )

    def _highlight_row(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> None:
        """Highlight entire rows matching condition."""
        condition = config.get("condition", {})
        style = config.get("style", {})

        for i, row in enumerate(dataset.rows):
            if self.evaluate_condition_group(condition, row):
                for column in dataset.columns:
                    context.add_highlight(
                        row_index=i,
                        column=column,
                        background_color=style.get("background_color"),
                        text_color=style.get("text_color"),
                        bold=style.get("bold", False),
                    )

    def _highlight_column(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> None:
        """Highlight entire column."""
        column = config.get("column", "")
        style = config.get("style", {})

        if column not in dataset.columns:
            context.add_warning(f"Column '{column}' not found for highlight")
            return

        for i in range(len(dataset.rows)):
            context.add_highlight(
                row_index=i,
                column=column,
                background_color=style.get("background_color"),
                text_color=style.get("text_color"),
                bold=style.get("bold", False),
            )

    def _highlight_gradient(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> None:
        """Apply color gradient based on values."""
        column = config.get("column", "")
        min_color = config.get("min_color", "#FFFFFF")
        max_color = config.get("max_color", "#0000FF")

        if column not in dataset.columns:
            context.add_warning(f"Column '{column}' not found for gradient")
            return

        values = []
        for row in dataset.rows:
            try:
                values.append(float(row.get(column, 0)))
            except (ValueError, TypeError):
                values.append(0)

        if not values:
            return

        min_val = min(values)
        max_val = max(values)
        val_range = max_val - min_val if max_val != min_val else 1

        for i, val in enumerate(values):
            ratio = (val - min_val) / val_range
            color = self._interpolate_color(min_color, max_color, ratio)
            context.add_highlight(
                row_index=i,
                column=column,
                background_color=color,
            )

    def _highlight_data_bar(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> None:
        """Add data bar indicators (stored as metadata)."""
        column = config.get("column", "")
        color = config.get("color", "#0066CC")

        if column not in dataset.columns:
            context.add_warning(f"Column '{column}' not found for data_bar")
            return

        values = []
        for row in dataset.rows:
            try:
                values.append(float(row.get(column, 0)))
            except (ValueError, TypeError):
                values.append(0)

        if not values:
            return

        max_val = max(abs(v) for v in values) or 1

        for i, val in enumerate(values):
            width_percent = abs(val) / max_val * 100
            context.set_variable(f"_databar_{i}_{column}", {
                "color": color,
                "width": width_percent,
            })

    @staticmethod
    def _interpolate_color(color1: str, color2: str, ratio: float) -> str:
        """Interpolate between two hex colors."""
        def hex_to_rgb(hex_color: str) -> tuple:
            hex_color = hex_color.lstrip("#")
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        def rgb_to_hex(rgb: tuple) -> str:
            return "#{:02x}{:02x}{:02x}".format(*rgb)

        r1, g1, b1 = hex_to_rgb(color1)
        r2, g2, b2 = hex_to_rgb(color2)

        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)

        return rgb_to_hex((r, g, b))
