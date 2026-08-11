import { WorkflowPageLayout } from "@/components/workflow/WorkflowPageLayout";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EXPORT_FORMAT_FIELD, REPORT_DATE_RANGE_FIELDS } from "@/features/workflows/reportConfigFields";
import { getReportDisplayName } from "@/utils/reportDisplayNames";

const settingsFields = [
  ...REPORT_DATE_RANGE_FIELDS,
  EXPORT_FORMAT_FIELD,
];

function Report18FilterSummary() {
  return (
    <Card className="border border-rail-line">
      <CardHeader className="border-b border-rail-line">
        <CardTitle>Portal filter summary</CardTitle>
        <CardDescription>
          Read-only settings applied on 18) Vande Bharat Report
        </CardDescription>
      </CardHeader>
      <CardBody className="grid gap-4 p-6 sm:grid-cols-2">
        <div className="rounded-xl border border-rail-line bg-surface/40 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Portal</p>
          <dl className="mt-3 space-y-2 text-sm text-slate-800">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Tab</dt>
              <dd className="text-right font-medium">18) Vande Bharat Report</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Portal page</dt>
              <dd className="text-right font-medium">Vande Bharat Train Report</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Zone</dt>
              <dd className="text-right font-medium">South Central Railway</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">From Date</dt>
              <dd className="text-right font-medium">Selected report date</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">To Date</dt>
              <dd className="text-right font-medium">Selected report date</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Other filters</dt>
              <dd className="text-right font-medium">Portal defaults</dd>
            </div>
          </dl>
        </div>
      </CardBody>
    </Card>
  );
}

export function Report18Page() {
  return (
    <WorkflowPageLayout
      reportId="report18"
      title={getReportDisplayName("report18")}
      description="Vande Bharat Report — dates only; other filters left at portal defaults"
      settingsFields={settingsFields}
      showAdvancedSettings
      beforeSettings={<Report18FilterSummary />}
    />
  );
}
