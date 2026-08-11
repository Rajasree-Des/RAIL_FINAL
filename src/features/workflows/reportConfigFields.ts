/** Shared advanced settings fields for report configuration pages */

import { defaultReportDateFrom, defaultReportDateTo } from "@/utils/reportDateRange";

export const DATE_FROM_FIELD = {
  id: "dateFrom",
  label: "From Date",
  type: "date" as const,
  value: defaultReportDateFrom(),
};

export const DATE_TO_FIELD = {
  id: "dateTo",
  label: "To Date",
  type: "date" as const,
  value: defaultReportDateTo(),
};

export const REPORT_DATE_RANGE_FIELDS = [DATE_FROM_FIELD, DATE_TO_FIELD];

export const HIGHLIGHT_RULES_FIELD = {
  id: "highlightRules",
  label: "Highlight Rules",
  type: "select" as const,
  value: "top_values",
  options: [
    { value: "top_values", label: "Highlight top values" },
    { value: "threshold", label: "Above threshold" },
    { value: "none", label: "None" },
  ],
};

export const EXPORT_FORMAT_FIELD = {
  id: "exportFormat",
  label: "Export Format",
  type: "select" as const,
  value: "xlsx",
  options: [
    { value: "xlsx", label: "Excel (.xlsx)" },
    { value: "pdf", label: "PDF" },
    { value: "csv", label: "CSV" },
  ],
};

export const COMPREHENSIVE_EXPORT_FORMAT_FIELD = {
  id: "exportFormat",
  label: "Export Format",
  type: "select" as const,
  value: "both",
  options: [
    { value: "xlsx", label: "Excel (.xlsx)" },
    { value: "pdf", label: "PDF" },
    { value: "both", label: "PDF and Excel" },
  ],
};

/** Fields still rendered in the advanced settings card (filters/columns are separate). */
export const COMMON_ADVANCED_FIELDS = [HIGHLIGHT_RULES_FIELD];
