/** Shared automation types — designed for Playwright event wiring. */

export type AutomationStepStatus = "waiting" | "running" | "completed" | "partial" | "failed";

export type AutomationRunStatus =
  | "idle"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "stopped"
  | "cancelled";

export type ActivityLogLevel = "info" | "success" | "warning" | "error";

export type ActivityLogSource = "playwright" | "pipeline" | "engine";

export interface AutomationStep {
  id: string;
  label: string;
  status: AutomationStepStatus;
  /** Backend error text for failed/partial steps (shown in timeline). */
  error?: string;
}

export interface AutomationReportOption {
  id: string;
  label: string;
  estimatedMinutes: number;
}

export interface AutomationActivityLogEntry {
  id: string;
  timestamp: Date;
  level: ActivityLogLevel;
  message: string;
  source: ActivityLogSource;
}

export interface AutomationCompletionSummary {
  reportsGenerated: number;
  dashboardUpdated: boolean;
  analyticsRefreshed: boolean;
  pdfsGenerated: number;
  executionTimeMs: number;
  runId?: string;
  downloadPdfAllUrl?: string;
  downloadExcelAllUrl?: string;
  /** Successful reports with downloadable PDFs */
  reportDownloads?: Array<{
    slug: string;
    datasetKey: string;
    pdfDownloadUrl: string;
    pdfPreviewUrl?: string;
    excelDownloadUrl?: string;
    status: string;
  }>;
}

export interface AutomationRunState {
  runStatus: AutomationRunStatus;
  selectedReportIds: string[];
  steps: AutomationStep[];
  activityLog: AutomationActivityLogEntry[];
  completionSummary: AutomationCompletionSummary | null;
  startedAt: number | null;
}

/**
 * Events expected from the Playwright automation engine.
 * Wire these via `handlePlaywrightEvent` when integration is ready.
 */
export type PlaywrightAutomationEvent =
  | { type: "run_started"; runId?: string }
  | { type: "step_started"; stepId: string; message?: string }
  | { type: "step_completed"; stepId: string; message?: string }
  | { type: "step_partial"; stepId: string; message?: string; error?: string }
  | { type: "step_failed"; stepId: string; message?: string; error?: string }
  | {
      type: "log";
      level: ActivityLogLevel;
      message: string;
      source?: ActivityLogSource;
    }
  | { type: "run_completed"; summary: AutomationCompletionSummary }
  | { type: "run_failed"; message?: string }
  | { type: "run_paused" }
  | { type: "run_resumed" };

export interface AutomationStepStats {
  completed: number;
  failed: number;
  running: number;
  waiting: number;
}
