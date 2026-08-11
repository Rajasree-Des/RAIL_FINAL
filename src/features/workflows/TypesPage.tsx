import { WorkflowPageLayout } from "@/components/workflow/WorkflowPageLayout";
import { COMMON_ADVANCED_FIELDS, EXPORT_FORMAT_FIELD, REPORT_DATE_RANGE_FIELDS } from "@/features/workflows/reportConfigFields";

const settingsFields = [
  ...REPORT_DATE_RANGE_FIELDS,
  { id: "topCount", label: "Top Count", type: "number" as const, value: 10, placeholder: "10" },
  {
    id: "sortBy",
    label: "Sort By",
    type: "select" as const,
    value: "count",
    options: [
      { value: "count", label: "Count" },
      { value: "category", label: "Category" },
    ],
  },
  EXPORT_FORMAT_FIELD,
];

export function TypesPage() {
  return (
    <WorkflowPageLayout
      reportId="types"
      title="Cause Wise Analysis"
      description="Configure and generate the cause-wise analysis report"
      settingsFields={settingsFields}
      advancedFields={COMMON_ADVANCED_FIELDS}
    />
  );
}
