from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.seed.seed_helpers import add_rule, add_template

PDF_TEMPLATE = "Official report prepared for competent authority review."
REPORT_WORKFLOWS = ["division-top-25", "train-no-top-20", "types-top-10", "scr-train", "scr-station"]


def seed_report_templates_and_rules(session: AsyncSession) -> None:
    for workflow_id in REPORT_WORKFLOWS:
        add_rule(
            session,
            workflow_id,
            "required-columns",
            "Required columns are present",
            "column_presence",
            "columns.required.all_present",
        )
        add_template(session, workflow_id, "official-pdf", "Official PDF", "pdf", PDF_TEMPLATE, "pdf")
        add_template(session, workflow_id, "official-summary", "Official Summary", "text", PDF_TEMPLATE, "text")


def seed_summary_templates(session: AsyncSession) -> None:
    wf = "summary-generation"
    add_template(session, wf, "ai-summary", "AI Summary", "text", "Consolidated railway intelligence summary.", "text")
    add_template(session, wf, "whatsapp", "WhatsApp Message", "whatsapp", "Railway Intelligence Summary — prepared for official circulation.", "text")
    add_template(session, wf, "email", "Official Email", "email", "Please find enclosed the consolidated intelligence summary.", "text")
