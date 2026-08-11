"""Execution context for rule engine."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Dataset:
    """Represents a tabular dataset for rule processing."""

    columns: list[str]
    rows: list[dict[str, Any]]
    name: str = "default"

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.columns)

    def copy(self) -> "Dataset":
        """Create a shallow copy of the dataset."""
        return Dataset(
            columns=self.columns.copy(),
            rows=[row.copy() for row in self.rows],
            name=self.name,
        )

    def to_dict_list(self) -> list[dict[str, Any]]:
        """Convert to list of dictionaries."""
        return self.rows

    @classmethod
    def from_dict_list(
        cls,
        data: list[dict[str, Any]],
        name: str = "default",
    ) -> "Dataset":
        """Create dataset from list of dictionaries."""
        if not data:
            return cls(columns=[], rows=[], name=name)

        columns = list(data[0].keys()) if data else []
        return cls(columns=columns, rows=data, name=name)


@dataclass
class Highlight:
    """Represents a cell highlight to apply."""

    row_index: int
    column: str
    background_color: str | None = None
    text_color: str | None = None
    bold: bool = False
    italic: bool = False


@dataclass
class LogEntry:
    """A single log entry for rule execution."""

    timestamp: datetime
    rule_id: str
    rule_name: str
    category: str
    message: str
    duration_ms: float
    rows_before: int
    rows_after: int
    success: bool


@dataclass
class ExecutionError:
    """A non-fatal error during rule execution."""

    rule_id: str
    rule_name: str
    message: str
    row_index: int | None = None


@dataclass
class ExecutionContext:
    """Context passed through rule execution pipeline."""

    template_id: str
    user_id: str | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    datasets: dict[str, Dataset] = field(default_factory=dict)
    highlights: list[Highlight] = field(default_factory=list)
    errors: list[ExecutionError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    execution_log: list[LogEntry] = field(default_factory=list)
    start_time: datetime | None = None
    timeout_seconds: float = 300.0
    max_rows: int = 1000000
    current_rule_id: str | None = None
    current_rule_name: str | None = None

    def add_highlight(
        self,
        row_index: int,
        column: str,
        background_color: str | None = None,
        text_color: str | None = None,
        bold: bool = False,
    ) -> None:
        """Add a highlight to the context."""
        self.highlights.append(
            Highlight(
                row_index=row_index,
                column=column,
                background_color=background_color,
                text_color=text_color,
                bold=bold,
            )
        )

    def add_error(
        self,
        message: str,
        row_index: int | None = None,
    ) -> None:
        """Add a non-fatal error."""
        self.errors.append(
            ExecutionError(
                rule_id=self.current_rule_id or "",
                rule_name=self.current_rule_name or "",
                message=message,
                row_index=row_index,
            )
        )

    def add_warning(self, message: str) -> None:
        """Add a warning."""
        self.warnings.append(message)

    def log_execution(
        self,
        rule_id: str,
        rule_name: str,
        category: str,
        message: str,
        duration_ms: float,
        rows_before: int,
        rows_after: int,
        success: bool = True,
    ) -> None:
        """Log a rule execution."""
        self.execution_log.append(
            LogEntry(
                timestamp=datetime.now(),
                rule_id=rule_id,
                rule_name=rule_name,
                category=category,
                message=message,
                duration_ms=duration_ms,
                rows_before=rows_before,
                rows_after=rows_after,
                success=success,
            )
        )

    def get_dataset(self, name: str) -> Dataset | None:
        """Get a named dataset."""
        return self.datasets.get(name)

    def set_dataset(self, name: str, dataset: Dataset) -> None:
        """Set a named dataset."""
        self.datasets[name] = dataset

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a runtime variable."""
        return self.variables.get(name, default)

    def set_variable(self, name: str, value: Any) -> None:
        """Set a runtime variable."""
        self.variables[name] = value


@dataclass
class ExecutionResult:
    """Result of rule execution."""

    success: bool
    dataset: Dataset
    highlights: list[Highlight]
    execution_log: list[LogEntry]
    errors: list[ExecutionError]
    warnings: list[str]
    rules_executed: int
    execution_time_ms: float
