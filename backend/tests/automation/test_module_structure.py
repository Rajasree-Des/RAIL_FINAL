"""Phase 1: verify automation package structure and imports."""

import importlib


MODULES = [
    "app.automation",
    "app.automation.browser",
    "app.automation.config",
    "app.automation.session",
    "app.automation.navigation",
    "app.automation.downloader",
    "app.automation.filters",
    "app.automation.generator",
    "app.automation.report1_filters",
    "app.automation.reports",
    "app.automation.selectors",
    "app.automation.utils",
    "app.automation.run",
]


def test_all_automation_modules_import():
    for module_name in MODULES:
        module = importlib.import_module(module_name)
        assert module is not None


def test_public_exports():
    from app.automation import (
        BrowserManager,
        NavigationService,
        ReportCatalog,
        ReportDownloader,
        SessionManager,
        config,
        run,
        selectors,
    )

    assert BrowserManager is not None
    assert SessionManager is not None
    assert NavigationService is not None
    assert ReportDownloader is not None
    assert ReportCatalog is not None
    assert selectors is not None
    assert config.chrome_debug_url
    assert callable(run)
