"""In-process Playwright automation package."""

from app.automation.browser import BrowserConnectionError, BrowserManager
from app.automation.config import AutomationConfig, config
from app.automation.downloader import ReportDownloader
from app.automation.navigation import NavigationService
from app.automation.reports import ReportCatalog, ReportDefinition
from app.automation.run import attach_to_railmadad, run
from app.automation.schemas import AutomationStartResult, MultiReportResult, ReportResult
from app.automation.selectors import PortalSelectors, selectors
from app.automation.session import AttachResult, RailMadadTabNotFoundError, SessionManager, TabInfo

__all__ = [
    "AttachResult",
    "AutomationConfig",
    "AutomationStartResult",
    "MultiReportResult",
    "ReportResult",
    "BrowserConnectionError",
    "BrowserManager",
    "NavigationService",
    "PortalSelectors",
    "RailMadadTabNotFoundError",
    "ReportCatalog",
    "ReportDefinition",
    "ReportDownloader",
    "SessionManager",
    "TabInfo",
    "config",
    "run",
    "selectors",
]
