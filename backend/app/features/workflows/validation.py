import re

from app.core.exceptions import ValidationError

VALID_ID_PATTERN = re.compile(r"^[a-z0-9-]+$")


def validate_workflow_id(workflow_id: str) -> None:
    if not workflow_id:
        raise ValidationError("Workflow ID cannot be empty", field="workflow_id")

    if len(workflow_id) > 64:
        raise ValidationError("Workflow ID exceeds maximum length of 64", field="workflow_id")

    if not VALID_ID_PATTERN.match(workflow_id):
        raise ValidationError(
            "Workflow ID must contain only lowercase letters, numbers, and hyphens",
            field="workflow_id",
        )
