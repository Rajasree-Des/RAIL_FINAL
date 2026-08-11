"""Default application setting definitions.

Four practical categories only: general, notifications, account.
(System information is served live by /system/info, not stored settings.)
"""

import json

SETTING_CATEGORIES = [
    {"slug": "general", "label": "General", "description": "Organization, time zone, and display formats"},
    {"slug": "notifications", "label": "Notifications", "description": "Report completion and failure alerts"},
    {"slug": "account", "label": "Account", "description": "Password and session preferences"},
]


def _def(
    category: str,
    key: str,
    label: str,
    value_type: str,
    default,
    *,
    description: str | None = None,
    validation: dict | None = None,
    options: list[dict] | None = None,
    sort_order: int = 0,
) -> dict:
    return {
        "category": category,
        "key": key,
        "label": label,
        "description": description,
        "value_type": value_type,
        "default_value": json.dumps(default),
        "validation_json": json.dumps(validation) if validation else None,
        "options_json": json.dumps(options) if options else None,
        "sort_order": sort_order,
        "is_editable": True,
    }


DEFAULT_SETTING_DEFINITIONS: list[dict] = [
    # General
    _def(
        "general", "organization_name", "Organization Name", "string",
        "South Central Railway",
        description="Shown in the sidebar and report branding",
        sort_order=1,
    ),
    _def(
        "general", "timezone", "Time Zone", "enum", "Asia/Kolkata",
        description="All displayed times use this time zone",
        options=[
            {"label": "India Standard Time (Asia/Kolkata)", "value": "Asia/Kolkata"},
            {"label": "UTC", "value": "UTC"},
        ],
        sort_order=2,
    ),
    _def(
        "general", "date_format", "Date Format", "enum", "DD/MM/YYYY",
        options=[
            {"label": "DD/MM/YYYY", "value": "DD/MM/YYYY"},
            {"label": "MM/DD/YYYY", "value": "MM/DD/YYYY"},
            {"label": "YYYY-MM-DD", "value": "YYYY-MM-DD"},
        ],
        sort_order=3,
    ),
    _def(
        "general", "time_format", "Time Format", "enum", "12h",
        options=[
            {"label": "12-hour (7:33 PM)", "value": "12h"},
            {"label": "24-hour (19:33)", "value": "24h"},
        ],
        sort_order=4,
    ),
    _def(
        "general", "default_page_size", "Default Page Size", "enum", 50,
        description="Rows per page in lists such as the Activity Log",
        options=[
            {"label": "10", "value": 10},
            {"label": "25", "value": 25},
            {"label": "50", "value": 50},
            {"label": "100", "value": 100},
        ],
        sort_order=5,
    ),
    # Notifications
    _def(
        "notifications", "enable_notifications", "Enable Notifications", "boolean", True,
        description="Master switch for all in-app alerts",
        sort_order=1,
    ),
    _def(
        "notifications", "notify_on_completion", "Notify on Report Completion", "boolean", True,
        sort_order=2,
    ),
    _def(
        "notifications", "notify_on_failure", "Notify on Report Failure", "boolean", True,
        sort_order=3,
    ),
    _def(
        "notifications", "notification_sound", "Notification Sound", "boolean", False,
        description="Play a short sound when a notification fires",
        sort_order=4,
    ),
    # Account
    _def(
        "account", "session_timeout", "Session Timeout", "enum", "30m",
        description="How long a signed-in session stays valid",
        options=[
            {"label": "15 minutes", "value": "15m"},
            {"label": "30 minutes", "value": "30m"},
            {"label": "1 hour", "value": "1h"},
            {"label": "Never", "value": "never"},
        ],
        sort_order=1,
    ),
]
