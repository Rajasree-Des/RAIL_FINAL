import { useCallback, useMemo, useState } from "react";
import { AUTOMATION_REPORTS, getEstimatedMinutes } from "@/features/automation/constants";
import type {
  AutomationActivityLogEntry,
  AutomationCompletionSummary,
  AutomationReportOption,
  AutomationRunState,
  AutomationRunStatus,
  AutomationStep,
  PlaywrightAutomationEvent,
} from "@/features/automation/types/automation";
import { buildAutomationSteps } from "@/features/automation/utils/buildSteps";
import { applyPlaywrightEvent } from "@/features/automation/utils/playwrightEvents";

const DEFAULT_REPORT_IDS = AUTOMATION_REPORTS.map((r) => r.id);

const INITIAL_STATE: AutomationRunState = {
  runStatus: "idle",
  selectedReportIds: DEFAULT_REPORT_IDS,
  steps: buildAutomationSteps(AUTOMATION_REPORTS, DEFAULT_REPORT_IDS),
  activityLog: [],
  completionSummary: null,
  startedAt: null,
};

export interface UseAutomationRunStateReturn {
  /** Full run state — pass to presentational components or Playwright bridge. */
  state: AutomationRunState;
  reports: AutomationReportOption[];
  allSelected: boolean;
  estimatedMinutes: number;
  /** Playwright event handler — wire this when engine integration is ready. */
  handlePlaywrightEvent: (event: PlaywrightAutomationEvent) => void;
  appendActivityLog: (entry: Omit<AutomationActivityLogEntry, "id" | "timestamp">) => void;
  setRunStatus: (status: AutomationRunStatus) => void;
  setSteps: (steps: AutomationStep[]) => void;
  setCompletionSummary: (summary: AutomationCompletionSummary | null) => void;
  toggleReport: (reportId: string, checked: boolean) => void;
  selectAllReports: (checked: boolean) => void;
  resetRun: (reportIds?: string[]) => void;
  prepareRun: (reportIds: string[]) => void;
}

function isRunLocked(runStatus: AutomationRunStatus): boolean {
  return runStatus === "running" || runStatus === "paused";
}

export function useAutomationRunState(): UseAutomationRunStateReturn {
  const [state, setState] = useState<AutomationRunState>(INITIAL_STATE);

  const reports = useMemo<AutomationReportOption[]>(
    () =>
      AUTOMATION_REPORTS.map(({ id, label, estimatedMinutes }) => ({
        id,
        label,
        estimatedMinutes,
      })),
    [],
  );

  const allSelected = state.selectedReportIds.length === reports.length;

  const estimatedMinutes = useMemo(
    () => getEstimatedMinutes(state.selectedReportIds),
    [state.selectedReportIds],
  );

  const handlePlaywrightEvent = useCallback((event: PlaywrightAutomationEvent) => {
    setState((prev) => ({
      ...prev,
      ...applyPlaywrightEvent(prev, event),
    }));
  }, []);

  const appendActivityLog = useCallback(
    (entry: Omit<AutomationActivityLogEntry, "id" | "timestamp">) => {
      setState((prev) => ({
        ...prev,
        activityLog: [
          ...prev.activityLog,
          {
            ...entry,
            id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
            timestamp: new Date(),
          },
        ],
      }));
    },
    [],
  );

  const setRunStatus = useCallback((runStatus: AutomationRunStatus) => {
    setState((prev) => ({ ...prev, runStatus }));
  }, []);

  const setSteps = useCallback((steps: AutomationStep[]) => {
    setState((prev) => ({ ...prev, steps }));
  }, []);

  const setCompletionSummary = useCallback((completionSummary: AutomationCompletionSummary | null) => {
    setState((prev) => ({ ...prev, completionSummary }));
  }, []);

  const resetRun = useCallback((reportIds?: string[]) => {
    const ids = reportIds ?? state.selectedReportIds;
    setState((prev) => ({
      ...prev,
      runStatus: "idle",
      selectedReportIds: ids,
      steps: buildAutomationSteps(AUTOMATION_REPORTS, ids),
      activityLog: [],
      completionSummary: null,
      startedAt: null,
    }));
  }, [state.selectedReportIds]);

  const prepareRun = useCallback((reportIds: string[]) => {
    setState((prev) => ({
      ...prev,
      runStatus: "running",
      selectedReportIds: reportIds,
      steps: buildAutomationSteps(AUTOMATION_REPORTS, reportIds),
      activityLog: [],
      completionSummary: null,
      startedAt: Date.now(),
    }));
  }, []);

  const toggleReport = useCallback(
    (reportId: string, checked: boolean) => {
      if (isRunLocked(state.runStatus)) return;

      setState((prev) => {
        const nextIds = checked
          ? [...prev.selectedReportIds, reportId]
          : prev.selectedReportIds.filter((id) => id !== reportId);

        return {
          ...prev,
          selectedReportIds: nextIds,
          steps: buildAutomationSteps(AUTOMATION_REPORTS, nextIds),
          completionSummary: null,
        };
      });
    },
    [state.runStatus],
  );

  const selectAllReports = useCallback(
    (checked: boolean) => {
      if (isRunLocked(state.runStatus)) return;

      const nextIds = checked ? reports.map((r) => r.id) : [];
      setState((prev) => ({
        ...prev,
        selectedReportIds: nextIds,
        steps: buildAutomationSteps(AUTOMATION_REPORTS, nextIds),
        completionSummary: null,
      }));
    },
    [reports, state.runStatus],
  );

  return {
    state,
    reports,
    allSelected,
    estimatedMinutes,
    handlePlaywrightEvent,
    appendActivityLog,
    setRunStatus,
    setSteps,
    setCompletionSummary,
    toggleReport,
    selectAllReports,
    resetRun,
    prepareRun,
  };
}
