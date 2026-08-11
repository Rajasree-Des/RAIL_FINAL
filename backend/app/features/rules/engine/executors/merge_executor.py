"""Merge rules executor."""

from collections import defaultdict
from typing import Any

from app.features.rules.engine.context import Dataset, ExecutionContext
from app.features.rules.engine.executors.base import BaseRuleExecutor
from app.infrastructure.database.models import ConfigurableRuleModel


class MergeRuleExecutor(BaseRuleExecutor):
    """Executor for merge rules."""

    async def execute(
        self,
        dataset: Dataset,
        rule: ConfigurableRuleModel,
        context: ExecutionContext,
    ) -> Dataset:
        """Execute merge rule."""
        config = self.get_config(rule)
        rule_type = rule.rule_type

        if rule_type == "join":
            return self._join(dataset, config, context)
        elif rule_type == "union":
            return self._union(dataset, config, context)
        elif rule_type == "compare":
            return self._compare(dataset, config, context)
        elif rule_type == "dedupe":
            return self._dedupe(dataset, config, context)
        elif rule_type == "conflict":
            return self._conflict(dataset, config, context)

        return dataset

    def _join(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Join with another dataset."""
        datasets = config.get("datasets", [])
        on = config.get("on", [])
        join_type = config.get("type", "left")

        if len(datasets) < 2:
            context.add_warning("Join requires at least 2 datasets")
            return dataset

        right_name = datasets[1] if len(datasets) > 1 else None
        right_dataset = context.get_dataset(right_name) if right_name else None

        if not right_dataset:
            context.add_warning(f"Dataset '{right_name}' not found for join")
            return dataset

        right_index: dict[tuple, list[dict]] = defaultdict(list)
        for row in right_dataset.rows:
            key = tuple(row.get(col) for col in on)
            right_index[key].append(row)

        left_columns = set(dataset.columns)
        right_columns = set(right_dataset.columns) - set(on)
        all_columns = list(dataset.columns) + [c for c in right_dataset.columns if c not in left_columns]

        new_rows = []

        if join_type in ("left", "inner", "outer"):
            for left_row in dataset.rows:
                key = tuple(left_row.get(col) for col in on)
                right_matches = right_index.get(key, [])

                if right_matches:
                    for right_row in right_matches:
                        merged = left_row.copy()
                        for col in right_columns:
                            merged[col] = right_row.get(col)
                        new_rows.append(merged)
                elif join_type in ("left", "outer"):
                    merged = left_row.copy()
                    for col in right_columns:
                        merged[col] = None
                    new_rows.append(merged)

        if join_type in ("right", "outer"):
            left_keys = {tuple(row.get(col) for col in on) for row in dataset.rows}
            for right_row in right_dataset.rows:
                key = tuple(right_row.get(col) for col in on)
                if key not in left_keys:
                    merged = {col: None for col in dataset.columns}
                    merged.update(right_row)
                    new_rows.append(merged)

        if join_type == "cross":
            new_rows = []
            for left_row in dataset.rows:
                for right_row in right_dataset.rows:
                    merged = left_row.copy()
                    for col in right_columns:
                        merged[col] = right_row.get(col)
                    new_rows.append(merged)

        return Dataset(columns=all_columns, rows=new_rows, name=dataset.name)

    def _union(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Stack datasets vertically."""
        datasets = config.get("datasets", [])
        dedupe = config.get("dedupe", True)

        all_rows = list(dataset.rows)
        all_columns = set(dataset.columns)

        for ds_name in datasets:
            if ds_name == dataset.name:
                continue
            other = context.get_dataset(ds_name)
            if other:
                all_rows.extend(other.rows)
                all_columns.update(other.columns)
            else:
                context.add_warning(f"Dataset '{ds_name}' not found for union")

        all_columns_list = list(all_columns)

        normalized_rows = []
        for row in all_rows:
            normalized = {col: row.get(col) for col in all_columns_list}
            normalized_rows.append(normalized)

        if dedupe:
            seen = set()
            unique_rows = []
            for row in normalized_rows:
                key = tuple(sorted(row.items()))
                if key not in seen:
                    seen.add(key)
                    unique_rows.append(row)
            normalized_rows = unique_rows

        return Dataset(columns=all_columns_list, rows=normalized_rows, name=dataset.name)

    def _compare(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Compare two datasets and mark differences."""
        dataset1_name = config.get("dataset1", "")
        dataset2_name = config.get("dataset2", "")
        key_columns = config.get("key_columns", [])
        compare_columns = config.get("compare_columns", [])

        ds1 = context.get_dataset(dataset1_name) or dataset
        ds2 = context.get_dataset(dataset2_name)

        if not ds2:
            context.add_warning(f"Dataset '{dataset2_name}' not found for compare")
            return dataset

        ds2_index: dict[tuple, dict] = {}
        for row in ds2.rows:
            key = tuple(row.get(col) for col in key_columns)
            ds2_index[key] = row

        new_columns = list(ds1.columns) + ["_compare_status", "_differences"]
        new_rows = []

        for row in ds1.rows:
            new_row = row.copy()
            key = tuple(row.get(col) for col in key_columns)
            ds2_row = ds2_index.get(key)

            if not ds2_row:
                new_row["_compare_status"] = "only_in_first"
                new_row["_differences"] = None
            else:
                differences = []
                for col in compare_columns:
                    val1 = row.get(col)
                    val2 = ds2_row.get(col)
                    if val1 != val2:
                        differences.append(f"{col}: {val1} -> {val2}")

                if differences:
                    new_row["_compare_status"] = "different"
                    new_row["_differences"] = "; ".join(differences)
                else:
                    new_row["_compare_status"] = "same"
                    new_row["_differences"] = None

            new_rows.append(new_row)

        ds1_keys = {tuple(row.get(col) for col in key_columns) for row in ds1.rows}
        for row in ds2.rows:
            key = tuple(row.get(col) for col in key_columns)
            if key not in ds1_keys:
                new_row = {col: None for col in ds1.columns}
                new_row.update(row)
                new_row["_compare_status"] = "only_in_second"
                new_row["_differences"] = None
                new_rows.append(new_row)

        return Dataset(columns=new_columns, rows=new_rows, name=dataset.name)

    def _dedupe(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Remove duplicate rows."""
        columns = config.get("columns", [])
        keep = config.get("keep", "first")

        if not columns:
            columns = dataset.columns

        seen: dict[tuple, int] = {}
        indices_to_keep = []

        for i, row in enumerate(dataset.rows):
            key = tuple(row.get(col) for col in columns)

            if key not in seen:
                seen[key] = i
                if keep != "none":
                    indices_to_keep.append(i)
            elif keep == "last":
                indices_to_keep.remove(seen[key])
                indices_to_keep.append(i)
                seen[key] = i

        new_rows = [dataset.rows[i] for i in sorted(indices_to_keep)]

        return Dataset(columns=dataset.columns, rows=new_rows, name=dataset.name)

    def _conflict(
        self,
        dataset: Dataset,
        config: dict,
        context: ExecutionContext,
    ) -> Dataset:
        """Apply conflict resolution strategy (used after other merge operations)."""
        context.set_variable("_conflict_strategy", config.get("strategy", "prefer_first"))
        context.set_variable("_conflict_priority", config.get("priority_dataset"))
        return dataset
