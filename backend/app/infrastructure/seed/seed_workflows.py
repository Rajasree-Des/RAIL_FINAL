import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import WorkflowModel
from app.infrastructure.seed.seed_columns import (
    MERGE_COLUMNS,
    STANDARD_COLUMNS,
    add_columns,
)
from app.infrastructure.seed.seed_settings import (
    seed_division_settings,
    seed_scr_station_settings,
    seed_scr_train_settings,
    seed_train_settings,
    seed_types_settings,
)
from app.infrastructure.seed.seed_templates import (
    seed_report_templates_and_rules,
    seed_summary_templates,
)
from app.infrastructure.seed.seed_workflow_definitions import get_workflow_definitions

logger = logging.getLogger(__name__)


async def seed_workflows(session: AsyncSession) -> None:
    existing = await session.execute(select(WorkflowModel.id).limit(1))
    if existing.scalar_one_or_none():
        logger.info("Workflows already seeded, skipping")
        return

    logger.info("Seeding workflow definitions")
    workflows = get_workflow_definitions()
    session.add_all(workflows)
    await session.flush()

    logger.info("Seeding column mappings")
    add_columns(session, "merging", MERGE_COLUMNS)
    for workflow_id in ["division-top-25", "train-no-top-20", "types-top-10", "scr-train", "scr-station"]:
        add_columns(session, workflow_id, STANDARD_COLUMNS)

    logger.info("Seeding workflow settings")
    seed_division_settings(session)
    seed_train_settings(session)
    seed_types_settings(session)
    seed_scr_train_settings(session)
    seed_scr_station_settings(session)

    logger.info("Seeding templates and rules")
    seed_report_templates_and_rules(session)
    seed_summary_templates(session)

    await session.commit()
    logger.info("Workflow seeding completed")
