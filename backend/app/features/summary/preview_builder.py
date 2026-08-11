"""Build truncated dataset preview for LLM context."""

from typing import Any

from app.core.config import settings


class PreviewBuilder:
    """Create a safe, truncated preview of dataset rows for LLM prompts."""

    DEFAULT_KEY_COLUMNS = [
        "division",
        "train_number",
        "complaint_type",
        "complaint_count",
        "status",
        "resolved_count",
    ]

    def build(
        self,
        rows: list[dict[str, Any]],
        max_rows: int | None = None,
        key_columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return truncated preview rows with selected columns only."""
        max_rows = max_rows or settings.summary_max_dataset_rows
        columns = key_columns or self._detect_columns(rows)

        preview: list[dict[str, Any]] = []
        for row in rows[:max_rows]:
            preview.append({col: row.get(col) for col in columns if col in row or col in row.keys()})

        if not preview and rows:
            for row in rows[:max_rows]:
                preview.append(dict(list(row.items())[:8]))

        return preview

    def build_text(
        self,
        rows: list[dict[str, Any]],
        max_rows: int | None = None,
    ) -> str:
        """Format preview as readable text for prompt inclusion."""
        preview = self.build(rows, max_rows)
        if not preview:
            return "No data rows available."

        lines: list[str] = []
        columns = list(preview[0].keys()) if preview else []
        lines.append(" | ".join(columns))
        lines.append("-" * 40)
        for row in preview:
            lines.append(" | ".join(str(row.get(c, "")) for c in columns))

        total = len(rows)
        shown = len(preview)
        if total > shown:
            lines.append(f"\n... showing {shown} of {total} rows")

        return "\n".join(lines)

    @staticmethod
    def _detect_columns(rows: list[dict[str, Any]]) -> list[str]:
        if not rows:
            return PreviewBuilder.DEFAULT_KEY_COLUMNS

        available = set(rows[0].keys())
        selected = [c for c in PreviewBuilder.DEFAULT_KEY_COLUMNS if c in available]
        if not selected:
            selected = list(rows[0].keys())[:8]
        return selected
