import type { ActivityEntry } from "@/api/activity";
import type { NotificationPrefs } from "@/utils/displayPrefs";
import {
  buildDedupeKey,
  isDuplicateEntry,
  isHistoricalEntry,
  markEntryNotified,
  type NotificationDedupeState,
  type TerminalKind,
} from "./notificationDedupe";
import { getReportDisplayName } from "./reportDisplayNames";

const COMPLETION_ACTIONS = new Set(["REPORT_COMPLETED", "AUTOMATION_COMPLETED"]);
const FAILURE_ACTIONS = new Set(["REPORT_FAILED", "AUTOMATION_FAILED"]);
const REPORT_TERMINAL_ACTIONS = new Set(["REPORT_COMPLETED", "REPORT_FAILED"]);
const AUTOMATION_TERMINAL_ACTIONS = new Set([
  "AUTOMATION_COMPLETED",
  "AUTOMATION_FAILED",
]);

const REPORT_DEFER_MS = 2000;

export interface NotificationHandlerDeps {
  showToast: (type: "success" | "error", title: string, message?: string) => void;
  playCompletionSound: () => void;
  playFailureSound: () => void;
}

export interface NotificationCoordinatorState {
  dedupe: NotificationDedupeState;
  cdpFinalRunIds: Set<string>;
  pendingReportTimers: Map<string, ReturnType<typeof setTimeout>>;
}

export function createNotificationCoordinatorState(
  subscribedAt?: number,
): NotificationCoordinatorState {
  return {
    dedupe: {
      keys: new Set(),
      entryIds: new Set(),
      subscribedAt: subscribedAt ?? Date.now(),
    },
    cdpFinalRunIds: new Set(),
    pendingReportTimers: new Map(),
  };
}

function truncateMessage(message: string, maxLength = 120): string {
  const trimmed = message.trim();
  if (trimmed.length <= maxLength) return trimmed;
  return `${trimmed.slice(0, maxLength - 1)}…`;
}

function terminalKindForEntry(entry: ActivityEntry): TerminalKind | null {
  if (FAILURE_ACTIONS.has(entry.action) || entry.status === "error") return "failed";
  if (COMPLETION_ACTIONS.has(entry.action)) return "success";
  return null;
}

function shouldNotify(
  entry: ActivityEntry,
  prefs: NotificationPrefs,
  terminalKind: TerminalKind,
): boolean {
  if (!prefs.enabled) return false;
  if (terminalKind === "failed") return prefs.onFailure;
  return prefs.onCompletion;
}

function buildToastContent(
  entry: ActivityEntry,
  terminalKind: TerminalKind,
): { type: "success" | "error"; title: string; message: string } {
  const failed = terminalKind === "failed";
  const isAutomation = AUTOMATION_TERMINAL_ACTIONS.has(entry.action);

  if (isAutomation) {
    return {
      type: failed ? "error" : "success",
      title: failed ? "Report generation failed" : "Report generation completed",
      message: failed
        ? truncateMessage(entry.message || "Report generation could not be completed.")
        : "All reports were generated successfully.",
    };
  }

  const reportName = getReportDisplayName(entry.report_slug);
  return {
    type: failed ? "error" : "success",
    title: failed ? "Report generation failed" : "Report generation completed",
    message: failed
      ? `${reportName} could not be generated.`
      : `${reportName} was generated successfully.`,
  };
}

function clearPendingReportTimer(
  state: NotificationCoordinatorState,
  runId: string,
): void {
  const timer = state.pendingReportTimers.get(runId);
  if (timer != null) {
    clearTimeout(timer);
    state.pendingReportTimers.delete(runId);
  }
}

function deliverNotification(
  entry: ActivityEntry,
  prefs: NotificationPrefs,
  terminalKind: TerminalKind,
  deps: NotificationHandlerDeps,
  state: NotificationCoordinatorState,
): void {
  if (!shouldNotify(entry, prefs, terminalKind)) return;
  if (isDuplicateEntry(entry, terminalKind, state.dedupe)) return;

  const toast = buildToastContent(entry, terminalKind);
  deps.showToast(toast.type, toast.title, toast.message);
  if (prefs.sound) {
    if (terminalKind === "failed") deps.playFailureSound();
    else deps.playCompletionSound();
  }
  markEntryNotified(entry, terminalKind, state.dedupe);
}

export function isSuppressedReportEvent(
  entry: ActivityEntry,
  state: NotificationCoordinatorState,
): boolean {
  if (!REPORT_TERMINAL_ACTIONS.has(entry.action)) return false;
  const runId = entry.run_id;
  return Boolean(runId && state.cdpFinalRunIds.has(runId));
}

export function handleNotificationActivity(
  entry: ActivityEntry,
  prefs: NotificationPrefs,
  deps: NotificationHandlerDeps,
  state: NotificationCoordinatorState,
): void {
  const terminalKind = terminalKindForEntry(entry);
  if (!terminalKind) return;
  if (isHistoricalEntry(entry, state.dedupe)) return;

  if (AUTOMATION_TERMINAL_ACTIONS.has(entry.action)) {
    const runId = entry.run_id;
    if (runId) {
      state.cdpFinalRunIds.add(runId);
      clearPendingReportTimer(state, runId);
    }
    deliverNotification(entry, prefs, terminalKind, deps, state);
    return;
  }

  if (REPORT_TERMINAL_ACTIONS.has(entry.action)) {
    if (isSuppressedReportEvent(entry, state)) return;

    const runId = entry.run_id;
    if (!runId) {
      deliverNotification(entry, prefs, terminalKind, deps, state);
      return;
    }

    clearPendingReportTimer(state, runId);
    state.pendingReportTimers.set(
      runId,
      setTimeout(() => {
        state.pendingReportTimers.delete(runId);
        if (state.cdpFinalRunIds.has(runId)) return;
        deliverNotification(entry, prefs, terminalKind, deps, state);
      }, REPORT_DEFER_MS),
    );
  }
}

export function disposeNotificationCoordinatorState(
  state: NotificationCoordinatorState,
): void {
  for (const runId of state.pendingReportTimers.keys()) {
    clearPendingReportTimer(state, runId);
  }
}

/** Exported for unit tests. */
export { buildDedupeKey, COMPLETION_ACTIONS, FAILURE_ACTIONS, REPORT_DEFER_MS };
