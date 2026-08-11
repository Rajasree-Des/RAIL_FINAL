import { WorkflowPageLayout } from "@/components/workflow/WorkflowPageLayout";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EXPORT_FORMAT_FIELD, REPORT_DATE_RANGE_FIELDS } from "@/features/workflows/reportConfigFields";
import { getReportDisplayName } from "@/utils/reportDisplayNames";

const settingsFields = [
  ...REPORT_DATE_RANGE_FIELDS,
  EXPORT_FORMAT_FIELD,
];

function Report9FilterSummary() {
  return (
    <Card className="border border-rail-line">
      <CardHeader className="border-b border-rail-line">
        <CardTitle>Portal filter summary</CardTitle>
        <CardDescription>
          Read-only Source A / Source B settings applied on tab 7) Mode Wise Cause Wise
        </CardDescription>
      </CardHeader>
      <CardBody className="grid gap-4 p-6 sm:grid-cols-2">
        <div className="rounded-xl border border-rail-line bg-surface/40 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Source A</p>
          <dl className="mt-3 space-y-2 text-sm text-slate-800">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Tab</dt>
              <dd className="text-right font-medium">7) Mode Wise Cause Wise</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Zone</dt>
              <dd className="text-right font-medium">ALL</dd>
            </div>
          </dl>
        </div>
        <div className="rounded-xl border border-rail-line bg-surface/40 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Source B</p>
          <dl className="mt-3 space-y-2 text-sm text-slate-800">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Tab</dt>
              <dd className="text-right font-medium">7) Mode Wise Cause Wise</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-500">Zone</dt>
              <dd className="text-right font-medium">South Central Railway</dd>
            </div>
          </dl>
        </div>
      </CardBody>
    </Card>
  );
}

export function Report9Page() {
  return (
    <WorkflowPageLayout
      reportId="report9"
      title={getReportDisplayName("report9")}
      description="Train/Station Cause Wise Grievances"
      settingsFields={settingsFields}
      showAdvancedSettings
      beforeSettings={<Report9FilterSummary />}
    />
  );
}
