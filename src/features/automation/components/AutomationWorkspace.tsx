import { Card, CardBody, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { AutomationActivityLog } from "@/features/automation/components/AutomationActivityLog";
import { AutomationCompletionSummaryCard } from "@/features/automation/components/AutomationCompletionSummary";
import { AutomationHero, AutomationToolbar } from "@/features/automation/components/AutomationToolbar";
import { AutomationProgressPanel } from "@/features/automation/components/AutomationProgressPanel";
import { AutomationReportSelector } from "@/features/automation/components/AutomationReportSelector";
import { AutomationStatusStrip } from "@/features/automation/components/AutomationStatusStrip";
import { formatEstimatedTime } from "@/features/automation/constants";
import type {
  AutomationActivityLogEntry,
  AutomationCompletionSummary,
  AutomationReportOption,
  AutomationRunStatus,
  AutomationStep,
} from "@/features/automation/types/automation";
import { cn } from "@/utils/cn";

export interface AutomationWorkspaceProps {
  reports: AutomationReportOption[];
  selectedReportIds: string[];
  allSelected: boolean;
  estimatedMinutes: number;
  steps: AutomationStep[];
  progressPercent: number;
  activityLog: AutomationActivityLogEntry[];
  completionSummary: AutomationCompletionSummary | null;
  runStatus: AutomationRunStatus;
  isBusy: boolean;
  isPaused: boolean;
  isRunning: boolean;
  isActive: boolean;
  acting: boolean;
  hasFailed: boolean;
  isComplete: boolean;
  onStart: () => void;
  onStop: () => void;
  onPause: () => void;
  onResume: () => void;
  onRefresh: () => void;
  onToggleReport: (reportId: string, checked: boolean) => void;
  onSelectAllReports: (checked: boolean) => void;
}

export function AutomationWorkspace(props: AutomationWorkspaceProps) {
  const {
    reports,
    selectedReportIds,
    allSelected,
    estimatedMinutes,
    steps,
    progressPercent,
    activityLog,
    completionSummary,
    isBusy,
    isPaused,
    isRunning,
    isActive,
    acting,
    hasFailed,
    isComplete,
    onStart,
    onStop,
    onPause,
    onResume,
    onRefresh,
    onToggleReport,
    onSelectAllReports,
  } = props;

  return (
    <div className="space-y-8">
      <AutomationStatusStrip
        isVisible={isBusy}
        isPaused={isPaused}
        progressPercent={progressPercent}
      />

      <AutomationToolbar
        acting={acting}
        isActive={isActive}
        isRunning={isRunning}
        isPaused={isPaused}
        onRefresh={onRefresh}
        onPause={onPause}
        onResume={onResume}
        onStop={onStop}
      />

      {!isBusy && !completionSummary && (
        <AutomationHero
          estimatedMinutesLabel={formatEstimatedTime(estimatedMinutes)}
          totalReports={reports.length}
          isBusy={isBusy}
          acting={acting}
          canStart={selectedReportIds.length > 0}
          onStart={onStart}
        />
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        {!isBusy && !completionSummary && (
          <div className="lg:col-span-2">
            <AutomationReportSelector
              reports={reports}
              selectedReportIds={selectedReportIds}
              allSelected={allSelected}
              disabled={isBusy}
              onToggleReport={onToggleReport}
              onSelectAllReports={onSelectAllReports}
            />
          </div>
        )}

        <Card className={cn(isBusy || completionSummary ? "lg:col-span-5" : "lg:col-span-3", "border-rail-line shadow-card")}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between gap-4">
              <div>
                <CardTitle className="text-base font-semibold">Report timeline</CardTitle>
                <CardDescription>Status of each report being generated</CardDescription>
              </div>
              {isBusy && !isPaused && <StatusBadge variant="info">In progress</StatusBadge>}
              {isComplete && <StatusBadge variant="success">Complete</StatusBadge>}
              {hasFailed && !isBusy && <StatusBadge variant="error">Failed</StatusBadge>}
            </div>
          </CardHeader>
          <CardBody>
            <AutomationProgressPanel
              steps={steps}
              progressPercent={progressPercent}
              isBusy={isBusy}
              isPaused={isPaused}
              hasFailed={hasFailed}
              isComplete={isComplete}
            />
          </CardBody>
        </Card>
      </div>

      {(isBusy || activityLog.length > 0) && (
        <AutomationActivityLog
          entries={activityLog}
          isLive={isBusy && !isPaused}
          emptyMessage="Activity will appear here during report generation."
        />
      )}

      {completionSummary && <AutomationCompletionSummaryCard summary={completionSummary} />}
    </div>
  );
}
