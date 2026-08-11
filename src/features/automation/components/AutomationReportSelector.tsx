import { Card, CardBody, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import type { AutomationReportOption } from "@/features/automation/types/automation";

export interface AutomationReportSelectorProps {
  reports: AutomationReportOption[];
  selectedReportIds: string[];
  allSelected: boolean;
  disabled: boolean;
  onToggleReport: (reportId: string, checked: boolean) => void;
  onSelectAllReports: (checked: boolean) => void;
}

export function AutomationReportSelector({
  reports,
  selectedReportIds,
  allSelected,
  disabled,
  onToggleReport,
  onSelectAllReports,
}: AutomationReportSelectorProps) {
  return (
    <Card className="border-rail-line shadow-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Reports to generate</CardTitle>
        <CardDescription>Select which daily reports to include</CardDescription>
      </CardHeader>
      <CardBody className="space-y-3">
        <Checkbox
          id="select-all-reports"
          checked={allSelected}
          disabled={disabled}
          onChange={(e) => onSelectAllReports(e.target.checked)}
          label={<span className="font-medium text-slate-900">All reports ({reports.length})</span>}
        />
        <div className="space-y-2">
          {reports.map((report) => (
            <Checkbox
              key={report.id}
              id={`report-${report.id}`}
              checked={selectedReportIds.includes(report.id)}
              disabled={disabled}
              onChange={(e) => onToggleReport(report.id, e.target.checked)}
              label={
                <>
                  <span>{report.label}</span>
                  <span className="text-xs font-normal text-slate-400">~{report.estimatedMinutes} min</span>
                </>
              }
            />
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
