import { WorkflowPageLayout } from "@/components/workflow/WorkflowPageLayout";
import { COMMON_ADVANCED_FIELDS, EXPORT_FORMAT_FIELD, REPORT_DATE_RANGE_FIELDS } from "@/features/workflows/reportConfigFields";

const settingsFields = [
  ...REPORT_DATE_RANGE_FIELDS,
  {
    id: "zone",
    label: "Zone",
    type: "select" as const,
    value: "scr",
    options: [{ value: "scr", label: "South Central Railway" }],
  },
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

export function SCRTrainPage() {
  return (
    <WorkflowPageLayout
      reportId="scr-train"
      title="SCR Train Report"
      description="Configure and generate the SCR train complaints report"
      settingsFields={settingsFields}
      advancedFields={COMMON_ADVANCED_FIELDS}
    />
  );
}
