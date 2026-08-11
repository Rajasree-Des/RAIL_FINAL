import {
  AUTOMATION_REPORTS,
  ESTIMATED_LOGIN_MINUTES,
} from "@/features/automation/constants";
import type {
  AutomationStep,
  AutomationStepStats,
  AutomationStepStatus,
} from "@/features/automation/types/automation";

export function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
}

export function formatRemainingTime(minutes: number): string {
  if (minutes <= 0) return "Less than 1 min";
  if (minutes < 60) return `~${minutes} min remaining`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `~${hours}h ${mins}m remaining` : `~${hours}h remaining`;
}

export function computeRemainingMinutes(steps: AutomationStep[]): number {
  let remaining = 0;

  for (const step of steps) {
    if (step.status !== "waiting" && step.status !== "running") continue;

    if (step.id === "login") {
      remaining += step.status === "running" ? 0.5 : ESTIMATED_LOGIN_MINUTES;
      continue;
    }

    const report = AUTOMATION_REPORTS.find((r) => r.id === step.id);
    if (report) {
      remaining +=
        step.status === "running" ? report.estimatedMinutes * 0.5 : report.estimatedMinutes;
    }
  }

  return Math.max(1, Math.ceil(remaining));
}

export function getStepStats(steps: AutomationStep[]): AutomationStepStats {
  return {
    completed: steps.filter((s) => s.status === "completed" || s.status === "partial").length,
    failed: steps.filter((s) => s.status === "failed").length,
    running: steps.filter((s) => s.status === "running").length,
    waiting: steps.filter((s) => s.status === "waiting").length,
  };
}

export function getCurrentTask(steps: AutomationStep[]): AutomationStep | undefined {
  return steps.find((s) => s.status === "running");
}

export function computeProgressPercent(steps: AutomationStep[]): number {
  if (steps.length === 0) return 0;
  const completed = steps.filter(
    (s) => s.status === "completed" || s.status === "partial",
  ).length;
  return Math.round((completed / steps.length) * 100);
}

export function statusLabel(status: AutomationStepStatus): string {
  switch (status) {
    case "completed":
      return "Done";
    case "partial":
      return "Partial";
    case "failed":
      return "Failed";
    case "running":
      return "Generating…";
    default:
      return "Waiting";
  }
}
