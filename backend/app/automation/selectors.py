"""CSS/XPath selectors for RailMadad portal automation (populated in later phases)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PortalSelectors:
    """Placeholder selector registry for portal UI elements."""

    login_username: str = ""
    login_password: str = ""
    login_submit: str = ""
    reports_menu: str = ""
    reports_table: str = ""
    report1_frame: str = "iframe[name='main'], iframe#main, iframe"
    report1_generate: str = (
        "input[type='submit'][value*='Submit'], button:has-text('Submit'), "
        "input[type='submit'][value*='Generate'], button:has-text('Generate'), "
        "input[type='submit'][value*='View'], button:has-text('View Report'), "
        "button:has-text('Show Report'), button:has-text('Search'), "
        "input[type='submit']"
    )
    report1_table: str = "table:has(tbody tr), table.dataTable, .report-table, #reportData"
    report1_grid: str = ".dataTables_wrapper table, .grid-table, [role='grid']"
    report1_from_date: str = ""
    report1_to_date: str = ""
    report1_received_header: str = (
        "table thead th:has-text('Received'), "
        ".dataTables_wrapper th:has-text('Received')"
    )
    report1_export: str = (
        "a:has-text('PDF'), button:has-text('PDF'), input[value*='PDF'], "
        "a:has-text('Export to Excel'), button:has-text('Export to Excel'), "
        "a:has-text('Export'), button:has-text('Export'), "
        "a:has-text('Download'), button:has-text('Download'), "
        "a:has-text('Excel'), button:has-text('Excel'), "
        "input[value*='Export'], input[value*='Download'], input[value*='Excel'], "
        "a[onclick*='export'], button[onclick*='export'], "
        "a[onclick*='excel'], button[onclick*='excel'], "
        "a[onclick*='pdf'], button[onclick*='pdf'], "
        "a[href*='export'], a[href*='download'], a[href*='xlsx'], a[href*='pdf'], "
        "#exportBtn, #downloadBtn, #pdfBtn, .export-btn, .download-btn"
    )
    report_print_button: str = (
        "a:has-text('Print'), button:has-text('Print'), "
        "input[value*='Print'], #printBtn, .print-btn, "
        "a[onclick*='print'], button[onclick*='print'], "
        "a:has-text('Print Report'), button:has-text('Print Report'), "
        "a:has-text('Print Preview'), button:has-text('Print Preview')"
    )


selectors = PortalSelectors()
