import type {
  AutomationActivityLogEntry,
  AutomationCompletionSummary,
  AutomationRunState,
  AutomationStep,
  PlaywrightAutomationEvent,
} from "@/features/automation/types/automation";

function createLogId(): string {
  return `log-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function appendLog(
  log: AutomationActivityLogEntry[],
  level: AutomationActivityLogEntry["level"],
  message: string,
  source: AutomationActivityLogEntry["source"] = "playwright",
): AutomationActivityLogEntry[] {
  return [
    ...log,
    {
      id: createLogId(),
      timestamp: new Date(),
      level,
      message,
      source,
    },
  ];
}

function updateStepStatus(
  steps: AutomationStep[],
  stepId: string,
  status: AutomationStep["status"],
  error?: string,
): AutomationStep[] {
  return steps.map((step) =>
    step.id === stepId
      ? {
          ...step,
          status,
          ...(error !== undefined ? { error } : status === "failed" ? {} : { error: undefined }),
        }
      : step,
  );
}

export interface PlaywrightEventResult {
  runStatus: AutomationRunState["runStatus"];
  steps: AutomationStep[];
  activityLog: AutomationActivityLogEntry[];
  completionSummary: AutomationCompletionSummary | null;
  startedAt: number | null;
}

/**
 * Pure reducer for Playwright events. Use via `handlePlaywrightEvent` in the run-state hook.
 */
export function applyPlaywrightEvent(
  state: Pick<
    AutomationRunState,
    "runStatus" | "steps" | "activityLog" | "completionSummary" | "startedAt"
  >,
  event: PlaywrightAutomationEvent,
): PlaywrightEventResult {
  switch (event.type) {
    case "run_started":
      return {
        runStatus: "running",
        steps: state.steps,
        activityLog: appendLog(
          state.activityLog,
          "info",
          event.runId
            ? `Report generation started (${event.runId})`
            : "Report generation started",
        ),
        completionSummary: null,
        startedAt: state.startedAt ?? Date.now(),
      };

    case "step_started":
      return {
        ...state,
        runStatus: "running",
        steps: updateStepStatus(state.steps, event.stepId, "running"),
        activityLog: appendLog(
          state.activityLog,
          "info",
          event.message ?? `Step started: ${event.stepId}`,
        ),
      };

    case "step_completed":
      return {
        ...state,
        steps: updateStepStatus(state.steps, event.stepId, "completed"),
        activityLog: appendLog(
          state.activityLog,
          "success",
          event.message ?? `Step completed: ${event.stepId}`,
        ),
      };

    case "step_partial":
      return {
        ...state,
        steps: updateStepStatus(
          state.steps,
          event.stepId,
          "partial",
          event.error ?? event.message,
        ),
        activityLog: appendLog(
          state.activityLog,
          "warning",
          event.message ?? event.error ?? `Step partial: ${event.stepId}`,
        ),
      };

    case "step_failed": {
      const steps = updateStepStatus(
        state.steps,
        event.stepId,
        "failed",
        event.error ?? event.message,
      );
      const othersStillActive = steps.some(
        (s) => s.id !== event.stepId && (s.status === "waiting" || s.status === "running"),
      );
      return {
        ...state,
        // Keep the run active when sibling reports continue; do not flash "Stopped".
        runStatus: othersStillActive ? "running" : "failed",
        steps,
        activityLog: appendLog(
          state.activityLog,
          "error",
          event.message ?? event.error ?? `Step failed: ${event.stepId}`,
        ),
      };
    }

    case "log":
      return {
        ...state,
        activityLog: appendLog(
          state.activityLog,
          event.level,
          event.message,
          event.source ?? "playwright",
        ),
      };

    case "run_completed":
      return {
        runStatus: "completed",
        steps: state.steps.map((s) =>
          s.status === "waiting" || s.status === "running"
            ? { ...s, status: "completed" as const }
            : s,
        ),
        activityLog: appendLog(state.activityLog, "success", "Report generation completed"),
        completionSummary: event.summary,
        startedAt: state.startedAt,
      };

    case "run_failed": {
      const failureMessage = event.message ?? "Report generation failed";
      return {
        ...state,
        runStatus: "failed",
        steps: state.steps.map((step) =>
          step.status === "waiting" || step.status === "running"
            ? { ...step, status: "failed" as const, error: failureMessage }
            : step,
        ),
        activityLog: appendLog(state.activityLog, "error", failureMessage),
      };
    }

    case "run_paused":
      return {
        ...state,
        runStatus: "paused",
        activityLog: appendLog(state.activityLog, "warning", "Report generation paused"),
      };

    case "run_resumed":
      return {
        ...state,
        runStatus: "running",
        activityLog: appendLog(state.activityLog, "info", "Report generation resumed"),
      };

    default:
      return state;
  }
}
