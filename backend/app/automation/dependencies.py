"""Dependency injection for in-process automation."""

from app.automation.service import AutomationService


def get_automation_service() -> AutomationService:
    return AutomationService()
