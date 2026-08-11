"""Main rule executor that orchestrates the execution pipeline."""

import json
import time
from datetime import datetime
from typing import Any

from app.features.rules.engine.context import (
    Dataset,
    ExecutionContext,
    ExecutionResult,
)
from app.features.rules.engine.executors.base import BaseRuleExecutor
from app.features.rules.engine.executors.calculation_executor import CalculationRuleExecutor
from app.features.rules.engine.executors.column_executor import ColumnRuleExecutor
from app.features.rules.engine.executors.conditional_executor import ConditionalRuleExecutor
from app.features.rules.engine.executors.filter_executor import FilterRuleExecutor
from app.features.rules.engine.executors.highlight_executor import HighlightRuleExecutor
from app.features.rules.engine.executors.merge_executor import MergeRuleExecutor
from app.features.rules.engine.executors.sorting_executor import SortingRuleExecutor
from app.features.rules.engine.executors.top_executor import TopRuleExecutor
from app.features.rules.repository import RuleRepository
from app.infrastructure.database.models import ConfigurableRuleModel


class RuleExecutor:
    """Orchestrates rule execution pipeline."""

    EXECUTION_ORDER = [
        "column",
        "conditional",
        "filter",
        "calculation",
        "merge",
        "sorting",
        "top",
        "highlight",
    ]

    def __init__(self, repository: RuleRepository):
        self.repository = repository
        self._executors: dict[str, BaseRuleExecutor] = {
            "column": ColumnRuleExecutor(),
            "conditional": ConditionalRuleExecutor(),
            "filter": FilterRuleExecutor(),
            "sorting": SortingRuleExecutor(),
            "top": TopRuleExecutor(),
            "highlight": HighlightRuleExecutor(),
            "calculation": CalculationRuleExecutor(),
            "merge": MergeRuleExecutor(),
        }

    async def execute(
        self,
        dataset: Dataset,
        template_id: str,
        context: ExecutionContext | None = None,
    ) -> ExecutionResult:
        """Execute all rules for a template."""
        start_time = time.time()

        if context is None:
            context = ExecutionContext(template_id=template_id)
        context.start_time = datetime.now()
        context.set_dataset(dataset.name, dataset)

        rules = await self.repository.get_by_template(template_id, include_global=True)

        rules_executed = 0

        for category in self.EXECUTION_ORDER:
            category_rules = self._filter_by_category(rules, category)
            category_rules = self._sort_by_priority(category_rules)

            for rule in category_rules:
                if not self._should_execute(rule, dataset, context):
                    continue

                context.current_rule_id = rule.id
                context.current_rule_name = rule.name

                executor = self._executors.get(rule.category)
                if executor is None:
                    context.add_warning(f"No executor for category: {rule.category}")
                    continue

                rule_start = time.time()
                rows_before = dataset.row_count

                try:
                    dataset = await executor.execute(dataset, rule, context)
                    rules_executed += 1

                    rule_duration = (time.time() - rule_start) * 1000
                    context.log_execution(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        category=rule.category,
                        message=f"Executed {rule.rule_type} rule",
                        duration_ms=rule_duration,
                        rows_before=rows_before,
                        rows_after=dataset.row_count,
                        success=True,
                    )

                except Exception as e:
                    rule_duration = (time.time() - rule_start) * 1000
                    context.log_execution(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        category=rule.category,
                        message=f"Error: {e}",
                        duration_ms=rule_duration,
                        rows_before=rows_before,
                        rows_after=dataset.row_count,
                        success=False,
                    )
                    context.add_error(str(e))

        execution_time = (time.time() - start_time) * 1000

        return ExecutionResult(
            success=len(context.errors) == 0,
            dataset=dataset,
            highlights=context.highlights,
            execution_log=context.execution_log,
            errors=context.errors,
            warnings=context.warnings,
            rules_executed=rules_executed,
            execution_time_ms=execution_time,
        )

    async def execute_single_rule(
        self,
        dataset: Dataset,
        rule: ConfigurableRuleModel,
        context: ExecutionContext | None = None,
    ) -> ExecutionResult:
        """Execute a single rule for testing purposes."""
        start_time = time.time()

        if context is None:
            context = ExecutionContext(template_id=rule.template_id or "test")
        context.start_time = datetime.now()
        context.current_rule_id = rule.id
        context.current_rule_name = rule.name

        executor = self._executors.get(rule.category)
        if executor is None:
            context.add_error(f"No executor for category: {rule.category}")
            return ExecutionResult(
                success=False,
                dataset=dataset,
                highlights=[],
                execution_log=[],
                errors=context.errors,
                warnings=context.warnings,
                rules_executed=0,
                execution_time_ms=0,
            )

        rows_before = dataset.row_count

        try:
            dataset = await executor.execute(dataset, rule, context)

            rule_duration = (time.time() - start_time) * 1000
            context.log_execution(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                message=f"Executed {rule.rule_type} rule",
                duration_ms=rule_duration,
                rows_before=rows_before,
                rows_after=dataset.row_count,
                success=True,
            )

        except Exception as e:
            rule_duration = (time.time() - start_time) * 1000
            context.log_execution(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                message=f"Error: {e}",
                duration_ms=rule_duration,
                rows_before=rows_before,
                rows_after=dataset.row_count,
                success=False,
            )
            context.add_error(str(e))

        execution_time = (time.time() - start_time) * 1000

        return ExecutionResult(
            success=len(context.errors) == 0,
            dataset=dataset,
            highlights=context.highlights,
            execution_log=context.execution_log,
            errors=context.errors,
            warnings=context.warnings,
            rules_executed=1 if len(context.errors) == 0 else 0,
            execution_time_ms=execution_time,
        )

    async def test_rule_config(
        self,
        category: str,
        rule_type: str,
        config: dict[str, Any],
        sample_data: list[dict[str, Any]],
        conditions: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Test a rule configuration against sample data."""
        dataset = Dataset.from_dict_list(sample_data, name="test")
        context = ExecutionContext(template_id="test")

        temp_rule = ConfigurableRuleModel(
            id="test-rule",
            name="Test Rule",
            category=category,
            rule_type=rule_type,
            config_json=json.dumps(config),
            conditions_json=json.dumps(conditions) if conditions else None,
            priority=0,
            is_enabled=True,
            is_global=False,
        )

        return await self.execute_single_rule(dataset, temp_rule, context)

    @staticmethod
    def _filter_by_category(
        rules: list[ConfigurableRuleModel],
        category: str,
    ) -> list[ConfigurableRuleModel]:
        """Filter rules by category."""
        return [r for r in rules if r.category == category]

    @staticmethod
    def _sort_by_priority(
        rules: list[ConfigurableRuleModel],
    ) -> list[ConfigurableRuleModel]:
        """Sort rules by priority."""
        return sorted(rules, key=lambda r: r.priority)

    def _should_execute(
        self,
        rule: ConfigurableRuleModel,
        dataset: Dataset,
        context: ExecutionContext,
    ) -> bool:
        """Check if rule should be executed based on conditions."""
        if not rule.is_enabled:
            return False

        if not rule.conditions_json:
            return True

        try:
            conditions = json.loads(rule.conditions_json)
            executor = self._executors.get(rule.category)
            if executor and hasattr(executor, "evaluate_condition_group"):
                for row in dataset.rows[:1]:
                    if executor.evaluate_condition_group(conditions, row):
                        return True
                return len(dataset.rows) == 0
        except (json.JSONDecodeError, Exception):
            pass

        return True
