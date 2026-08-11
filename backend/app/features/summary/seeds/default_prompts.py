"""Default prompt templates for seeding."""

DEFAULT_PROMPT_TEMPLATES = [
    {
        "name": "Executive Summary",
        "slug": "executive-summary",
        "summary_type": "executive",
        "description": "Comprehensive executive summary with complaints overview and recommendations",
        "is_default": True,
        "output_format": "markdown",
        "system_prompt": (
            "You are writing an executive summary for railway complaint intelligence reports. "
            "Use formal, professional language suitable for senior officers. "
            "Structure: Overview, Key Metrics, Top Observations, Recommendations."
        ),
        "user_prompt_template": """Report: {{ metadata.report_name }}
Period: {{ metadata.report_period }}
{% if metadata.division %}Division: {{ metadata.division }}{% endif %}

STATISTICS (use exactly as provided — do NOT recalculate):
- Total complaints: {{ statistics.total_complaints }}
- Resolved: {{ statistics.resolved_complaints }} ({{ statistics.resolution_rate }}%)
- Pending: {{ statistics.pending_complaints }}
- Unsatisfactory feedback: {{ statistics.unsatisfactory_count }} ({{ statistics.unsatisfactory_rate }}%)

Pre-computed daily highlights:
{% for h in statistics.daily_highlights %}- {{ h }}
{% endfor %}

Pre-computed key observations:
{% for o in statistics.key_observations %}- {{ o }}
{% endfor %}

Top complaint types:
{% for t in statistics.top_complaint_types %}- {{ t.name }}: {{ t.count }} ({{ t.percentage }}%)
{% endfor %}

Write an executive summary covering overall complaints, resolved/pending status, top observations, and actionable recommendations for railway officers.""",
    },
    {
        "name": "WhatsApp Summary",
        "slug": "whatsapp-summary",
        "summary_type": "whatsapp",
        "description": "Short bullet-point summary for WhatsApp sharing",
        "is_default": True,
        "output_format": "bullets",
        "max_tokens": 512,
        "system_prompt": (
            "You are writing a concise WhatsApp message for railway officers. "
            "Keep it under 500 characters if possible. Use bullet points with *bold* markers. "
            "Professional but brief language."
        ),
        "user_prompt_template": """Report: {{ metadata.report_name }} | Period: {{ metadata.report_period }}

FACTS (use exactly):
- Total: {{ statistics.total_complaints }} | Resolved: {{ statistics.resolved_complaints }} ({{ statistics.resolution_rate }}%) | Pending: {{ statistics.pending_complaints }}

Highlights:
{% for h in statistics.daily_highlights %}- {{ h }}
{% endfor %}

Write a short WhatsApp-ready summary with bullet points.""",
    },
    {
        "name": "Official Email Draft",
        "slug": "official-email",
        "summary_type": "email",
        "description": "Formal email with subject, greeting, body, and closing",
        "is_default": True,
        "output_format": "plain_text",
        "system_prompt": (
            "You are drafting an official email for railway administration. "
            "Include: Subject line, formal greeting, summary body, professional closing. "
            "Use formal government correspondence tone."
        ),
        "user_prompt_template": """Report: {{ metadata.report_name }}
Period: {{ metadata.report_period }}
{% if metadata.included_reports %}Included reports: {{ metadata.included_reports | join(', ') }}{% endif %}

STATISTICS (use exactly):
- Total complaints: {{ statistics.total_complaints }}
- Resolved: {{ statistics.resolved_complaints }} ({{ statistics.resolution_rate }}%)
- Pending: {{ statistics.pending_complaints }}

Key highlights:
{% for h in statistics.daily_highlights %}- {{ h }}
{% endfor %}

Draft an official email with Subject, Greeting, Summary body, and Closing.""",
    },
    {
        "name": "Daily Highlights",
        "slug": "daily-highlights",
        "summary_type": "daily_highlights",
        "description": "Bullet list of daily highlights from pre-computed facts",
        "is_default": True,
        "output_format": "bullets",
        "max_tokens": 512,
        "temperature": 0.2,
        "system_prompt": (
            "Format the provided daily highlights into a clean bullet list. "
            "Do NOT add new facts or numbers — only reformat what is given."
        ),
        "user_prompt_template": """Report: {{ metadata.report_name }} | Period: {{ metadata.report_period }}

Pre-computed daily highlights (format as bullet list, do not change numbers):
{% for h in statistics.daily_highlights %}- {{ h }}
{% endfor %}

Additional context — top divisions:
{% for d in statistics.top_divisions %}- {{ d.name }}: {{ d.count }}
{% endfor %}

Format these as a professional daily highlights bullet list.""",
    },
    {
        "name": "Key Observations",
        "slug": "key-observations",
        "summary_type": "key_observations",
        "description": "Key observations derived from pre-computed analysis",
        "is_default": True,
        "output_format": "bullets",
        "max_tokens": 512,
        "temperature": 0.2,
        "system_prompt": (
            "Present key observations as a bullet list. "
            "Use ONLY the provided observations — do not infer new conclusions or numbers."
        ),
        "user_prompt_template": """Report: {{ metadata.report_name }} | Period: {{ metadata.report_period }}

Pre-computed key observations:
{% for o in statistics.key_observations %}- {{ o }}
{% endfor %}

Supporting statistics:
- Resolution rate: {{ statistics.resolution_rate }}%
- Unsatisfactory rate: {{ statistics.unsatisfactory_rate }}%

Format as a professional key observations bullet list for officers.""",
    },
]
