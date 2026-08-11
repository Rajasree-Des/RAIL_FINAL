from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import ColumnMappingModel

STANDARD_COLUMNS = [
    ("train", "Train", "text", True, "Train No"),
    ("division", "Division", "text", True, "Division"),
    ("score", "Score", "number", False, "Score"),
    ("complaints", "Complaints", "number", False, "Complaints"),
    ("status", "Status", "status", False, "Status"),
]

MERGE_COLUMNS = [
    ("source", "Source File", "text", False, "Source File"),
    ("train", "Train", "text", True, "Train No"),
    ("division", "Division", "text", True, "Division"),
    ("score", "Score", "number", False, "Score"),
    ("complaints", "Complaints", "number", False, "Complaints"),
]


def add_columns(
    session: AsyncSession,
    workflow_id: str,
    columns: list[tuple[str, str, str, bool, str]],
) -> None:
    for index, (key, label, col_type, required, source) in enumerate(columns):
        session.add(
            ColumnMappingModel(
                workflow_id=workflow_id,
                key=key,
                label=label,
                column_type=col_type,
                required=required,
                source_column=source,
                sort_order=index,
            )
        )
