import { WorkflowPageLayout } from "@/components/workflow/WorkflowPageLayout";
import {
  COMMON_ADVANCED_FIELDS,
  EXPORT_FORMAT_FIELD,
  REPORT_DATE_RANGE_FIELDS,
} from "@/features/workflows/reportConfigFields";

const settingsFields = [
  ...REPORT_DATE_RANGE_FIELDS,
  {
    id: "division",
    label: "Division",
    type: "select" as const,
    value: "all",
    options: [
      { value: "all", label: "All Divisions" },
      { value: "secunderabad", label: "Secunderabad" },
      { value: "hyderabad", label: "Hyderabad" },
      { value: "vijayawada", label: "Vijayawada" },
    ],
  },
  {
    id: "reportType",
    label: "Report Type",
    type: "select" as const,
    value: "complaints",
    options: [
      { value: "complaints", label: "Complaints" },
      { value: "feedback", label: "Feedback" },
      { value: "both", label: "Complaints & Feedback" },
    ],
  },
  EXPORT_FORMAT_FIELD,
];

const previewColumns = [
  { key: "zone", header: "Zone" },
  { key: "complaints", header: "Complaints" },
  { key: "feedback", header: "Feedback" },
  { key: "total", header: "Total" },
];

export function MergingPage() {
  return (
    <WorkflowPageLayout
      reportId="merging"
      title="Zone Wise Report"
      description="Configure and generate the zone-wise complaints and feedback report"
      settingsFields={settingsFields}
      advancedFields={COMMON_ADVANCED_FIELDS}
      previewColumns={previewColumns}
    />
  );
}
