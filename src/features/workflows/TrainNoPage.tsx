import { WorkflowPageLayout } from "@/components/workflow/WorkflowPageLayout";
import { COMMON_ADVANCED_FIELDS, EXPORT_FORMAT_FIELD, REPORT_DATE_RANGE_FIELDS } from "@/features/workflows/reportConfigFields";

const settingsFields = [
  ...REPORT_DATE_RANGE_FIELDS,
  { id: "topCount", label: "Top Count", type: "number" as const, value: 20, placeholder: "20" },
  {
    id: "sortBy",
    label: "Sort By",
    type: "select" as const,
    value: "count",
    options: [
      { value: "count", label: "Complaint Count" },
      { value: "train", label: "Train Number" },
    ],
  },
  EXPORT_FORMAT_FIELD,
];

export function TrainNoPage() {
  return (
    <WorkflowPageLayout
      reportId="train-no"
      title="Top 20 Trains"
      description="Configure and generate the top 20 complaint trains report"
      settingsFields={settingsFields}
      advancedFields={COMMON_ADVANCED_FIELDS}
    />
  );
}
