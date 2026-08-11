import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { automationApi, type AutomationRunDetail, type ReportResult } from "@/api/automation";
import { useAutomationDashboard } from "@/features/admin/automation/hooks/useAutomationDashboard";
import type { AutomationWorkspaceProps } from "@/features/automation/components/AutomationWorkspace";
import { useAutomationRunState } from "@/features/automation/hooks/useAutomationRunState";
import { computeProgressPercent, getStepStats } from "@/features/automation/utils/display";
import { mergeActivityLogs } from "@/features/automation/utils/mapApiLogs";
import {
  CLEAR_GENERATION_UI_EVENT,
  RAILMADAD_ACTIVE_GENERATION_KEY,
  RAILMADAD_LAST_RUN_KEY,
  clearGenerationSessionState,
} from "@/features/automation/utils/generationSession";

const LAST_RUN_KEY = RAILMADAD_LAST_RUN_KEY;
const ACTIVE_SESSION_KEY = RAILMADAD_ACTIVE_GENERATION_KEY;

/** Check if a run status is active (not terminal) and should restore progress UI. */
export function isActiveRunStatus(status: string): boolean {
  return (
    status === "queued" ||
    status === "pending" ||
    status === "running" ||
    status === "extracting" ||
    status === "processing" ||
    status === "paused" ||
    status === "pause_requested" ||
    status === "stopping"
  );
}

export function isTerminalRunStatus(status: string): boolean {
  return (
    status === "completed" ||
    status === "failed" ||
    status === "stopped" ||
    status === "cancelled"
  );
}

/** UI report ids → backend canonical slugs */
const UI_TO_BACKEND: Record<string, string> = {
  zone: "report1",
  division: "division",
  train: "train-no",
  cause: "types",
  "scr-train": "scr-train",
  "scr-station": "scr-station",
  report9: "report9",
  "comprehensive-10-13": "comprehensive-10-13",
  report14: "report14",
  report18: "report18",
  "bottom-report": "bottom-report",
};

const BACKEND_TO_UI: Record<string, string> = Object.fromEntries(
  Object.entries(UI_TO_BACKEND).map(([ui, backend]) => [backend, ui]),
);

function toBackendSlugs(uiIds: string[]): string[] {
  return uiIds.map((id) => UI_TO_BACKEND[id] ?? id);
}

function stepIdForSlug(slug: string): string {
  return BACKEND_TO_UI[slug] ?? slug;
}

function downloadsFromReports(reports: ReportResult[]) {
  return reports
    .filter((r) => r.status === "success" && r.pdf_download_url)
    .map((r) => ({
      slug: r.slug,
      datasetKey: r.dataset_key ?? r.slug,
      pdfDownloadUrl: r.pdf_download_url as string,
      pdfPreviewUrl: r.pdf_preview_url ?? undefined,
      excelDownloadUrl: r.excel_download_url ?? undefined,
      status: r.status,
    }));
}

function applyRunDetailToEvents(
  detail: AutomationRunDetail,
  seen: Set<string>,
  emit: (event: Parameters<ReturnType<typeof useAutomationRunState>["handlePlaywrightEvent"]>[0]) => void,
  activeRunId?: string | null,
) {
  // Ignore stale run payloads from a previous generation.
  if (activeRunId && detail.run_id && detail.run_id !== activeRunId) {
    return;
  }

  for (const report of detail.reports ?? []) {
    const stepId = stepIdForSlug(report.slug);
    const key = `${report.slug}:${report.status}:${report.processing_success ? 1 : 0}`;
    if (seen.has(key)) continue;
    seen.add(key);

    // Non-terminal deferred markers must not flip the step to Generating forever.
    // Leftover pending error on status=success is a merge bug; treat as completed.
    const pendingDeferred =
      report.status === "partial_success" &&
      typeof report.error === "string" &&
      report.error.toLowerCase().includes("ingest/process pending");

    if (pendingDeferred) {
      emit({
        type: "step_started",
        stepId,
        message: report.error ?? `${report.slug} processing`,
      });
      continue;
    }

    if (report.status === "success") {
      emit({ type: "step_completed", stepId, message: `${report.slug} ready` });
      continue;
    }

    if (report.status === "partial_success") {
      // Terminal partial — never leave UI on Generating.
      emit({
        type: "step_partial",
        stepId,
        message: report.error ?? `${report.slug} partial success`,
        error: report.error ?? undefined,
      });
    } else if (report.status === "failed") {
      emit({
        type: "step_failed",
        stepId,
        message: report.error ?? `${report.slug} failed`,
        error: report.error ?? undefined,
      });
    } else if (report.status === "skipped") {
      emit({
        type: "step_failed",
        stepId,
        message: report.error ?? `${report.slug} skipped`,
        error: report.error ?? undefined,
      });
    }
  }

  if (detail.status === "completed" || detail.status === "failed") {
    const downloads = downloadsFromReports(detail.reports ?? []);
    const reports = detail.reports ?? [];
    const terminalPending = (report: (typeof reports)[number]) =>
      report.status === "partial_success" &&
      typeof report.error === "string" &&
      report.error.toLowerCase().includes("ingest/process pending");
    const allReportsSuccessful = reports.every(
      (report) => report.status === "success" || report.status === "skipped",
    );
    const hasMixedResults =
      (detail.reports_successful ?? 0) > 0 && (detail.reports_failed ?? 0) > 0;
    const hasTerminalPartial = reports.some(
      (report) => report.status === "partial_success" && !terminalPending(report),
    );
    if (
      (detail.status === "completed" && allReportsSuccessful) ||
      (detail.status === "failed" && hasMixedResults)
    ) {
      emit({
        type: "run_completed",
        summary: {
          reportsGenerated: downloads.length || detail.reports_successful,
          dashboardUpdated: true,
          analyticsRefreshed: true,
          pdfsGenerated: downloads.length,
          executionTimeMs: Math.round((detail.total_duration_seconds ?? 0) * 1000),
          runId: detail.run_id,
          downloadPdfAllUrl: detail.download_pdf_all_url ?? undefined,
          downloadExcelAllUrl: detail.download_excel_all_url ?? undefined,
          reportDownloads: downloads,
        },
      });
    } else if (hasTerminalPartial || hasMixedResults || detail.status === "failed") {
      emit({
        type: "run_failed",
        message:
          detail.error ??
          (hasTerminalPartial
            ? "Report generation completed with partial reports"
            : "Automation finished with errors"),
      });
    } else {
      emit({
        type: "run_failed",
        message: detail.error ?? "Automation failed",
      });
    }
  }

  if (detail.status === "stopped" || detail.status === "cancelled") {
    for (const report of detail.reports ?? []) {
      const stepId = stepIdForSlug(report.slug);
      const stepKey = `${report.slug}:stopped`;
      if (seen.has(stepKey)) continue;
      seen.add(stepKey);
      if (report.status !== "success" && report.status !== "partial_success" && report.status !== "failed") {
        emit({
          type: "step_failed",
          stepId,
          message: "Stopped",
        });
      }
    }
  }
}

export interface UseAutomationPageReturn extends AutomationWorkspaceProps {
  loading: boolean;
  handlePlaywrightEvent: ReturnType<typeof useAutomationRunState>["handlePlaywrightEvent"];
  showLoginDialog: boolean;
  onCloseLoginDialog: () => void;
  showChromeDialog: boolean;
  onCloseChromeDialog: () => void;
  chromeConnectionDetail: string | null;
  /** True only after the user clicks Generate in this session. */
  generationStarted: boolean;
  failureMessage?: string;
  isStopped?: boolean;
  onDismiss: () => void;
}

/**
 * Page-level container: async start + poll run status into live progress.
 */
export function useAutomationPage(): UseAutomationPageReturn {
  const {
    loading,
    acting,
    isPaused,
    logs: apiLogs,
    startInProcess,
    stop,
    pause,
    resume,
    refresh,
  } = useAutomationDashboard(2000);

  const runState = useAutomationRunState();
  const { state, appendActivityLog, handlePlaywrightEvent, prepareRun, resetRun } = runState;

  const [showLoginDialog, setShowLoginDialog] = useState(false);
  const [showChromeDialog, setShowChromeDialog] = useState(false);
  const [chromeConnectionDetail, setChromeConnectionDetail] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  /** Progress UI is gated on this — never open from stale engine/DB/HMR state. */
  const [generationStarted, setGenerationStarted] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const seenRef = useRef<Set<string>>(new Set());
  const activeRunIdRef = useRef<string | null>(null);
  const stoppingRef = useRef(false);
  const pausingRef = useRef(false);
  const lastPolledStatusRef = useRef<string | null>(null);

  const activityLog = useMemo(
    () => mergeActivityLogs(state.activityLog, apiLogs),
    [state.activityLog, apiLogs],
  );

  const progressPercent = computeProgressPercent(state.steps);
  const stepStats = getStepStats(state.steps);
  const isStopped =
    state.runStatus === "stopped" || state.runStatus === "cancelled";
  const hasErrors =
    !isStopped &&
    (stepStats.failed > 0 || state.runStatus === "failed");
  const hasFailed = hasErrors;
  const failureMessage = useMemo(() => {
    if (!hasFailed) return undefined;
    for (let i = activityLog.length - 1; i >= 0; i -= 1) {
      if (activityLog[i].level === "error") return activityLog[i].message;
    }
    return undefined;
  }, [activityLog, hasFailed]);
  const isBusy =
    acting ||
    stopping ||
    state.runStatus === "running" ||
    state.runStatus === "paused" ||
    Boolean(activeRunIdRef.current);
  const hasPartialSteps = state.steps.some((s) => s.status === "partial");
  const isComplete =
    state.completionSummary != null &&
    state.runStatus === "completed" &&
    !hasPartialSteps &&
    stepStats.failed === 0;

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const clearActiveRunState = useCallback(() => {
    stopPolling();
    activeRunIdRef.current = null;
    seenRef.current = new Set();
    clearGenerationSessionState();
  }, [stopPolling]);

  const markGenerationSession = useCallback((runId: string) => {
    try {
      localStorage.setItem(LAST_RUN_KEY, runId);
      sessionStorage.setItem(ACTIVE_SESSION_KEY, runId);
    } catch {
      // ignore
    }
  }, []);

  const pollRun = useCallback(
    async (runId: string) => {
      try {
        const detail = await automationApi.getRun(runId);
        if (stoppingRef.current) return;
        if (activeRunIdRef.current && activeRunIdRef.current !== runId) return;
        applyRunDetailToEvents(detail, seenRef.current, handlePlaywrightEvent, activeRunIdRef.current);
        if (detail.status === "failed") {
          const errorCode = detail.result?.error_code;
          if (errorCode === "RAILMADAD_NOT_LOGGED_IN") {
            setShowLoginDialog(true);
          }
        }
        const prev = lastPolledStatusRef.current;
        lastPolledStatusRef.current = detail.status;
        if (
          (detail.status === "paused" || detail.status === "pause_requested") &&
          prev !== "paused" &&
          prev !== "pause_requested"
        ) {
          handlePlaywrightEvent({ type: "run_paused" });
        }
        if (
          detail.status === "running" &&
          (prev === "paused" || prev === "pause_requested")
        ) {
          handlePlaywrightEvent({ type: "run_resumed" });
        }
        if (isTerminalRunStatus(detail.status)) {
          stopPolling();
          activeRunIdRef.current = null;
          // Clear session key but keep localStorage for result page until dismissed
          try {
            sessionStorage.removeItem(ACTIVE_SESSION_KEY);
          } catch {
            // ignore
          }
          if (detail.status === "stopped" || detail.status === "cancelled") {
            // Fully clear state and return to landing page for stopped runs
            clearGenerationSessionState();
            setGenerationStarted(false);
            resetRun();
          }
          // For completed/failed - keep generationStarted=true to show result page
        }
      } catch (error) {
        console.error("Failed to poll run", error);
      }
    },
    [handlePlaywrightEvent, resetRun, stopPolling],
  );

  const startPolling = useCallback(
    (runId: string) => {
      stopPolling();
      activeRunIdRef.current = runId;
      seenRef.current = new Set();
      lastPolledStatusRef.current = null;
      void pollRun(runId);
      pollRef.current = setInterval(() => void pollRun(runId), 2000);
    },
    [pollRun, stopPolling],
  );

  // Track whether we've already attempted restoration this mount
  const restorationAttemptedRef = useRef(false);

  // Helper to clear all stale generation state
  const clearStaleState = useCallback(() => {
    stopPolling();
    activeRunIdRef.current = null;
    seenRef.current = new Set();
    lastPolledStatusRef.current = null;
    stoppingRef.current = false;
    pausingRef.current = false;
    setGenerationStarted(false);
    setStopping(false);
    resetRun();
    try {
      sessionStorage.removeItem(ACTIVE_SESSION_KEY);
      localStorage.removeItem(LAST_RUN_KEY);
    } catch {
      // ignore
    }
  }, [resetRun, stopPolling]);

  // On mount: always show landing page, never auto-restore progress view
  // The progress view should ONLY appear after user explicitly clicks Generate
  useEffect(() => {
    const resetUi = () => {
      clearStaleState();
      restorationAttemptedRef.current = false;
    };

    const initializeLandingPage = async () => {
      if (restorationAttemptedRef.current) return;
      restorationAttemptedRef.current = true;

      // ALWAYS show landing page on mount/refresh/login
      // Never auto-restore progress view based on backend state
      setGenerationStarted(false);
      setStopping(false);
      activeRunIdRef.current = null;
      seenRef.current = new Set();
      lastPolledStatusRef.current = null;

      // Clear any stale storage hints from previous sessions
      try {
        sessionStorage.removeItem(ACTIVE_SESSION_KEY);
        localStorage.removeItem(LAST_RUN_KEY);
      } catch {
        // ignore
      }
    };

    void initializeLandingPage();

    window.addEventListener(CLEAR_GENERATION_UI_EVENT, resetUi);
    return () => {
      window.removeEventListener(CLEAR_GENERATION_UI_EVENT, resetUi);
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount/login only
  }, []);

  const onStart = useCallback(async (options?: { date_from?: string; date_to?: string }) => {
    if (state.selectedReportIds.length === 0) return;
    // Block if generation is already in progress or an active run exists
    if (
      generationStarted ||
      state.runStatus === "running" ||
      state.runStatus === "paused" ||
      stopping ||
      acting ||
      activeRunIdRef.current
    ) {
      return;
    }

    const reportIds = state.selectedReportIds;
    setGenerationStarted(true);
    prepareRun(reportIds);
    handlePlaywrightEvent({ type: "run_started" });
    handlePlaywrightEvent({ type: "step_started", stepId: "login" });

    appendActivityLog({
      level: "info",
      message: "Connecting to RailMadad via Playwright…",
      source: "playwright",
    });

    if (options?.date_from && options?.date_to) {
      console.info(
        "home_full_run: selected_date_from=%s selected_date_to=%s generation_source=home_full_run",
        options.date_from,
        options.date_to,
      );
    }

    const slugs = toBackendSlugs(reportIds);
    const result = await startInProcess({
      report_slugs: slugs,
      async_mode: true,
      date_from: options?.date_from,
      date_to: options?.date_to,
    });

    if (result?.error_code === "RAILMADAD_NOT_LOGGED_IN") {
      setShowLoginDialog(true);
      setGenerationStarted(false);
      resetRun();
      return;
    }

    if (result?.error_code === "SERVICE_UNAVAILABLE") {
      setGenerationStarted(false);
      resetRun();
      return;
    }

    if (
      result?.error_code === "BROWSER_CONNECTION_ERROR" ||
      (result && !result.success && !result.run_id)
    ) {
      setChromeConnectionDetail(result?.error ?? null);
      setShowChromeDialog(true);
      setGenerationStarted(false);
      resetRun();
      return;
    }

    if (result?.run_id) {
      markGenerationSession(result.run_id);
      handlePlaywrightEvent({ type: "step_completed", stepId: "login" });
      handlePlaywrightEvent({ type: "run_started", runId: result.run_id });
      appendActivityLog({
        level: "success",
        message: `Automation started (run ${result.run_id})`,
        source: "playwright",
      });
      startPolling(result.run_id);
      return;
    }

    // Sync fallback (full result returned)
    if (result?.success) {
      handlePlaywrightEvent({ type: "step_completed", stepId: "login" });
      for (const report of result.reports ?? []) {
        const stepId = stepIdForSlug(report.slug);
        if (report.status === "success") {
          handlePlaywrightEvent({ type: "step_completed", stepId });
        } else {
          handlePlaywrightEvent({
            type: "step_failed",
            stepId,
            error: report.error ?? undefined,
          });
        }
      }
      const downloads = downloadsFromReports(result.reports ?? []);
      if (result.run_id) {
        markGenerationSession(result.run_id);
      }
      handlePlaywrightEvent({
        type: "run_completed",
        summary: {
          reportsGenerated: downloads.length || (result.reports?.length ?? 0),
          dashboardUpdated: true,
          analyticsRefreshed: true,
          pdfsGenerated: downloads.length,
          executionTimeMs: Math.round((result.total_duration_seconds ?? 0) * 1000),
          runId: result.run_id ?? undefined,
          downloadPdfAllUrl: result.download_pdf_all_url ?? undefined,
          downloadExcelAllUrl: result.download_excel_all_url ?? undefined,
          reportDownloads: downloads,
        },
      });
      return;
    }

    setGenerationStarted(false);
    resetRun();
    appendActivityLog({
      level: "error",
      message: result?.error ?? "Playwright could not connect to RailMadad",
      source: "playwright",
    });
  }, [
    acting,
    appendActivityLog,
    generationStarted,
    handlePlaywrightEvent,
    markGenerationSession,
    prepareRun,
    resetRun,
    startInProcess,
    startPolling,
    state.runStatus,
    state.selectedReportIds,
    stopping,
  ]);

  const onDismiss = useCallback(() => {
    clearActiveRunState();
    setGenerationStarted(false);
    resetRun();
  }, [clearActiveRunState, resetRun]);

  const onStop = useCallback(async () => {
    if (stoppingRef.current || stopping) return;
    const runId =
      activeRunIdRef.current ??
      (() => {
        try {
          return localStorage.getItem(LAST_RUN_KEY);
        } catch {
          return null;
        }
      })();
    if (!runId) {
      clearActiveRunState();
      setGenerationStarted(false);
      resetRun();
      return;
    }

    stoppingRef.current = true;
    setStopping(true);
    // Unblock any in-progress pause wait
    pausingRef.current = false;
    try {
      const ok = await stop(runId);
      if (!ok) {
        return;
      }
      clearActiveRunState();
      setGenerationStarted(false);
      resetRun();
      await refresh();
    } finally {
      stoppingRef.current = false;
      setStopping(false);
    }
  }, [clearActiveRunState, refresh, resetRun, stop, stopping]);

  const onPause = useCallback(async () => {
    if (stoppingRef.current || stopping || pausingRef.current) return;
    const runId =
      activeRunIdRef.current ??
      (() => {
        try {
          return localStorage.getItem(LAST_RUN_KEY);
        } catch {
          return null;
        }
      })();
    if (!runId) return;

    pausingRef.current = true;
    // Optimistic UI — do not wait for worker to reach paused
    handlePlaywrightEvent({ type: "run_paused" });
    try {
      const ok = await pause(runId);
      if (!ok) {
        handlePlaywrightEvent({ type: "run_resumed" });
        return;
      }
      lastPolledStatusRef.current = "pause_requested";
    } finally {
      pausingRef.current = false;
    }
  }, [handlePlaywrightEvent, pause, stopping]);

  const onResume = useCallback(async () => {
    if (stoppingRef.current || stopping || pausingRef.current) return;
    const runId =
      activeRunIdRef.current ??
      (() => {
        try {
          return localStorage.getItem(LAST_RUN_KEY);
        } catch {
          return null;
        }
      })();
    if (!runId) return;

    pausingRef.current = true;
    handlePlaywrightEvent({ type: "run_resumed" });
    try {
      const ok = await resume(runId);
      if (!ok) {
        handlePlaywrightEvent({ type: "run_paused" });
        return;
      }
      lastPolledStatusRef.current = "running";
    } finally {
      pausingRef.current = false;
    }
  }, [handlePlaywrightEvent, resume, stopping]);

  return {
    loading,
    acting: acting || stopping,
    isBusy: generationStarted && isBusy,
    isPaused: isPaused || state.runStatus === "paused",
    isRunning: generationStarted && state.runStatus === "running",
    isActive:
      generationStarted &&
      (state.runStatus === "running" || state.runStatus === "paused"),
    isComplete: generationStarted && isComplete,
    hasFailed: generationStarted && hasErrors,
    isStopped: generationStarted && isStopped,
    generationStarted,
    progressPercent,
    activityLog,
    reports: runState.reports,
    allSelected: runState.allSelected,
    estimatedMinutes: runState.estimatedMinutes,
    selectedReportIds: state.selectedReportIds,
    steps: state.steps,
    runStatus: state.runStatus,
    completionSummary: state.completionSummary,
    onToggleReport: runState.toggleReport,
    onSelectAllReports: runState.selectAllReports,
    onStart,
    onStop,
    onPause,
    onResume,
    onRefresh: refresh,
    handlePlaywrightEvent,
    showLoginDialog,
    onCloseLoginDialog: () => setShowLoginDialog(false),
    showChromeDialog,
    onCloseChromeDialog: () => setShowChromeDialog(false),
    chromeConnectionDetail,
    failureMessage,
    onDismiss,
  };
}
