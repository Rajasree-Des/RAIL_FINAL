"""Deterministic Daily Summary feature (post-run briefing)."""

DAILY_SUMMARY_TYPE = "daily_briefing"
DAILY_SUMMARY_MODEL = "deterministic_template"

TERMINAL_REPORT_STATUSES = frozenset(
    {"success", "partial_success", "failed", "stopped", "skipped"}
)

SUMMARY_SOURCE_SLUGS = (
    "report1",
    "division",
    "train-no",
    "types",
    "scr-train",
    "scr-station",
    "report9",
    "comprehensive-10-13",
)
