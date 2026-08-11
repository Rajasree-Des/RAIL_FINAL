import { WorkflowPageLayout } from "@/components/workflow/WorkflowPageLayout";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EXPORT_FORMAT_FIELD, REPORT_DATE_RANGE_FIELDS } from "@/features/workflows/reportConfigFields";
import { getReportDisplayName } from "@/utils/reportDisplayNames";

const settingsFields = [...REPORT_DATE_RANGE_FIELDS, EXPORT_FORMAT_FIELD];

function PortalFilterSummary() {
  return (
    <Card className="border border-rail-line">
      <CardHeader className="border-b border-rail-line">
        <CardTitle>Portal filter summary</CardTitle>
        <CardDescription>Read-only portal sources for all four sections</CardDescription>
      </CardHeader>
      <CardBody className="grid gap-4 p-6 sm:grid-cols-2">
        <FilterBlock
          title="Security"
          rows={[
            ["Tab", "Comprehensive (with drill down)"],
            ["Zone", "South Central Railway"],
            ["Division", "ALL"],
            ["Type", "Security-Train"],
            ["View", "Division Wise"],
          ]}
        />
        <FilterBlock
          title="Punctuality"
          rows={[
            ["Tab", "Comprehensive (with drill down)"],
            ["Zone", "South Central Railway"],
            ["Division", "ALL"],
            ["Type", "Punctuality-Train"],
            ["View", "Division Wise"],
          ]}
        />
        <FilterBlock
          title="Electrical Equipment"
          rows={[
            ["Tab", "Comprehensive (with drill down)"],
            ["Zone", "South Central Railway"],
            ["Division", "ALL"],
            ["Type", "Electrical Equipment-Train"],
            ["View", "Division Wise"],
          ]}
        />
        <FilterBlock
          title="Water Availability"
          rows={[
            ["Tab", "11) Train Watering Complaint"],
            ["Zone", "South Central Railway"],
            ["Division", "ALL"],
            ["View", "Division Wise"],
            ["Output", "Previous Watering Point"],
          ]}
        />
      </CardBody>
    </Card>
  );
}

function FilterBlock({
  title,
  rows,
}: {
  title: string;
  rows: [string, string][];
}) {
  return (
    <div className="rounded-xl border border-rail-line bg-surface/40 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <dl className="mt-3 space-y-2 text-sm text-slate-800">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-3">
            <dt className="text-slate-500">{label}</dt>
            <dd className="text-right font-medium">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function ThresholdSummary() {
  return (
    <Card className="border border-rail-line">
      <CardHeader className="border-b border-rail-line">
        <CardTitle>Threshold summary</CardTitle>
        <CardDescription>Read-only business rules applied during generation</CardDescription>
      </CardHeader>
      <CardBody className="space-y-2 p-6 text-sm text-slate-800">
        <p>Division Received threshold: 20 or more</p>
        <p>Trains shown only when complaint count is 2 or more</p>
        <p>SC Owning Rly cells highlighted in output</p>
      </CardBody>
    </Card>
  );
}

export function BottomReportPage() {
  return (
    <WorkflowPageLayout
      reportId="bottom-report"
      title={getReportDisplayName("bottom-report")}
      description="Bottom performed trains — division drill-down and train frequency analysis"
      settingsFields={settingsFields}
      showAdvancedSettings={false}
      beforeSettings={
        <>
          <PortalFilterSummary />
          <ThresholdSummary />
        </>
      }
    />
  );
}
