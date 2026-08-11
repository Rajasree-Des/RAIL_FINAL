import { WorkflowPageLayout } from "@/components/workflow/WorkflowPageLayout";
import {
  COMMON_ADVANCED_FIELDS,
  EXPORT_FORMAT_FIELD,
  REPORT_DATE_RANGE_FIELDS,
} from "@/features/workflows/reportConfigFields";

const settingsFields = [
  ...REPORT_DATE_RANGE_FIELDS,
  {
    id: "topCount",
    label: "Top Count",
    type: "number" as const,
    value: 25,
    placeholder: "25",
  },
  {
    id: "sortBy",
    label: "Sort By",
    type: "select" as const,
    value: "count",
    options: [
      { value: "count", label: "Count (Descending)" },
      { value: "division", label: "Division Name" },
      { value: "percentage", label: "Percentage" },
    ],
  },
  EXPORT_FORMAT_FIELD,
];

const previewColumns = [
  { key: "rank", header: "Rank", width: "60px" },
  { key: "division", header: "Division" },
  { key: "count", header: "Count" },
  { key: "percentage", header: "Percentage" },
  { key: "change", header: "Change" },
];

export function DivisionPage() {
  return (
    <WorkflowPageLayout
      reportId="division"
      title="Division (Bottom 25)"
      description="Configure and generate the division-wise bottom 25 report"
      settingsFields={settingsFields}
      advancedFields={COMMON_ADVANCED_FIELDS}
      previewColumns={previewColumns}
    />
  );
}
