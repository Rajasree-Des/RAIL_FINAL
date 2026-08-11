import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { RailMadadLoginDialog } from "@/features/automation/components/RailMadadLoginDialog";
import { ChromeConnectionDialog } from "@/features/automation/components/ChromeConnectionDialog";
import { HomeGenerationProgress } from "@/features/home/components/HomeGenerationProgress";
import { HomeGenerationTimeline } from "@/features/home/components/HomeGenerationTimeline";
import { HomeQuickActions } from "@/features/home/components/HomeQuickActions";
import { HomeRecentActivity } from "@/features/home/components/HomeRecentActivity";
import { HomeReportsGrid } from "@/features/home/components/HomeReportsGrid";
import { HomeStatsGrid } from "@/features/home/components/HomeStatsGrid";
import { HomeWelcomeSection } from "@/features/home/components/HomeWelcomeSection";
import { METRIC_ICONS } from "@/features/home/homeData";
import {
  currentStatusDisplay,
  expectedTimeDescription,
  formatExpectedTime,
  formatLastGenerated,
  generatedReportsValue,
  lastGeneratedDescription,
  reportsAvailableDescription,
} from "@/features/home/dashboardDisplay";
import { useDashboardSummary } from "@/features/home/hooks/useDashboardSummary";
import { useAutomationPage } from "@/features/automation/hooks/useAutomationPage";
import { usePermissions } from "@/hooks/usePermissions";
import {
  defaultReportDateFrom,
  defaultReportDateTo,
  validateReportDateRange,
} from "@/utils/reportDateRange";

function pipelineStepFromProgress(percent: number, isRunning: boolean): number {
  if (!isRunning) return 0;
  if (percent >= 100) return 5;
  if (percent >= 75) return 4;
  if (percent >= 50) return 3;
  if (percent >= 25) return 2;
  return 1;
}

export function HomePage() {
  const { isAdmin } = usePermissions();
  const generation = useAutomationPage();
  const { summary, loading: summaryLoading } = useDashboardSummary();

  const [dateFrom, setDateFrom] = useState(defaultReportDateFrom);
  const [dateTo, setDateTo] = useState(defaultReportDateTo);

  const dateRangeError = validateReportDateRange(dateFrom, dateTo);
  const isDateRangeValid = dateRangeError === null;

  const statusDisplay = summary
    ? currentStatusDisplay(summary.current_status)
    : { label: summaryLoading ? "Loading…" : "Ready", description: "No generation in progress" };

  const metrics = [
    {
      icon: METRIC_ICONS.lastGenerated,
      title: "Last Generated",
      value: summary ? formatLastGenerated(summary.last_generated_at) : "—",
      description: summary ? lastGeneratedDescription(summary) : "Loading…",
    },
    {
      icon: METRIC_ICONS.reportsAvailable,
      title: "Generated Reports",
      value: summary ? generatedReportsValue(summary) : "—",
      description: summary ? reportsAvailableDescription(summary) : "Loading…",
    },
    {
      icon: METRIC_ICONS.expectedTime,
      title: "Expected Time",
      value: summary
        ? formatExpectedTime(
            summary.estimated_duration_seconds,
            summary.default_expected_duration_seconds,
          )
        : "—",
      description: summary
        ? expectedTimeDescription(summary.estimated_duration_seconds)
        : "Loading…",
    },
    {
      icon: METRIC_ICONS.currentStatus,
      title: "Current Status",
      value: statusDisplay.label,
      description: statusDisplay.description,
      accent: true,
    },
  ];

  // Strict gate: progress UI only after an explicit Generate click in this session.
  const started = generation.generationStarted === true;
  const isGenerating =
    started &&
    (generation.runStatus === "running" || generation.runStatus === "paused");
  const showProgress =
    started &&
    (isGenerating ||
      generation.runStatus === "completed" ||
      generation.runStatus === "failed" ||
      generation.isComplete ||
      generation.hasFailed);

  const pipelineStep = pipelineStepFromProgress(
    generation.progressPercent,
    isGenerating,
  );

  if (showProgress && isAdmin) {
    return (
      <>
        <RailMadadLoginDialog
          open={generation.showLoginDialog}
          onClose={generation.onCloseLoginDialog}
        />
        <ChromeConnectionDialog
          open={generation.showChromeDialog}
          onClose={generation.onCloseChromeDialog}
          detail={generation.chromeConnectionDetail}
        />
        <div className="animate-fade-in space-y-8">
          <div className="grid gap-6 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <HomeGenerationProgress
                steps={generation.steps}
                progressPercent={generation.progressPercent}
                isBusy={generation.isBusy}
                isPaused={generation.isPaused}
                hasFailed={generation.hasFailed}
                isStopped={generation.isStopped}
                isComplete={generation.isComplete}
                acting={generation.acting}
                failureMessage={generation.failureMessage}
                onPause={generation.onPause}
                onResume={generation.onResume}
                onStop={generation.onStop}
              />
            </div>
            <div className="lg:col-span-2">
              <HomeGenerationTimeline activeStep={pipelineStep} isRunning={isGenerating} />
            </div>
          </div>
          {!generation.isComplete && (
            <div className="flex justify-center">
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  void (generation.hasFailed ? generation.onDismiss() : generation.onStop())
                }
              >
                {generation.hasFailed ? "Back to home" : "Cancel generation"}
              </Button>
            </div>
          )}
        </div>
      </>
    );
  }

  return (
    <>
      <RailMadadLoginDialog
        open={generation.showLoginDialog}
        onClose={generation.onCloseLoginDialog}
      />
      <ChromeConnectionDialog
        open={generation.showChromeDialog}
        onClose={generation.onCloseChromeDialog}
        detail={generation.chromeConnectionDetail}
      />
      <div className="space-y-12 pb-4">
        <HomeWelcomeSection
          isAdmin={isAdmin}
          isStarting={generation.acting && !showProgress}
          onGenerate={() => void generation.onStart({ date_from: dateFrom, date_to: dateTo })}
          disabled={generation.selectedReportIds.length === 0 || !isDateRangeValid}
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
          dateRangeError={dateRangeError}
        />

        <HomeStatsGrid metrics={metrics} />

        <HomeReportsGrid liveReports={summary?.reports} />

        <HomeRecentActivity />

        <HomeQuickActions />
      </div>
    </>
  );
}
