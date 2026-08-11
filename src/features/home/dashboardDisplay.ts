/** Pure mapping from dashboard summary data to Home card copy. */

import type { DashboardStatus, DashboardSummary } from "@/api/dashboard";
import {
  formatTime12h,
  istDayKey,
  parseBackendTimestamp,
} from "@/utils/datetime";

export interface StatusDisplay {
  label: string;
  description: string;
}

const STATUS_DISPLAY: Record<DashboardStatus, StatusDisplay> = {
  ready: { label: "Ready", description: "No generation in progress" },
  pending: { label: "Ready", description: "No generation in progress" },
  running: { label: "Running", description: "Generation in progress" },
  processing: { label: "Processing", description: "Preparing report outputs" },
  paused: { label: "Paused", description: "Generation paused" },
  success: { label: "Completed", description: "Latest run finished successfully" },
  partial_success: {
    label: "Partial Success",
    description: "Some reports need attention",
  },
  failed: { label: "Failed", description: "Latest run failed" },
  stopped: { label: "Stopped", description: "Latest run was stopped" },
  skipped: { label: "Skipped", description: "Latest run was skipped" },
};

export function currentStatusDisplay(status: DashboardStatus): StatusDisplay {
  return STATUS_DISPLAY[status] ?? STATUS_DISPLAY.ready;
}

/** Per-report pill label; terminal partial_success is never "Generating". */
export function reportStatusLabel(status: DashboardStatus): string {
  switch (status) {
    case "success":
      return "Generated";
    case "partial_success":
      return "Partial";
    case "failed":
      return "Failed";
    case "stopped":
      return "Stopped";
    case "skipped":
      return "Skipped";
    case "running":
    case "processing":
      return "Generating";
    default:
      return "Ready";
  }
}

export function formatLastGenerated(iso: string | null): string {
  const date = parseBackendTimestamp(iso);
  if (!date) return "Never";
  const now = new Date();
  const time = formatTime12h(date);
  if (istDayKey(date) === istDayKey(now)) return `Today ${time}`;
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  if (istDayKey(date) === istDayKey(yesterday)) {
    return `Yesterday ${time}`;
  }
  return `${date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
  })} ${time}`;
}

export function lastGeneratedDescription(summary: DashboardSummary): string {
  if (!summary.last_generated_at || !summary.last_run_status) {
    return "No completed runs yet";
  }
  const total = summary.total_enabled_reports;
  if (summary.last_run_status === "success") {
    const n = summary.successful_report_count || total;
    return `All ${n} reports completed successfully`;
  }
  if (summary.last_run_status === "partial_success") {
    return `${summary.successful_report_count} succeeded, ${summary.failed_report_count} failed`;
  }
  if (summary.last_run_status === "stopped") {
    return "Last run was stopped";
  }
  return "Last run failed";
}

export function formatExpectedTime(
  seconds: number | null,
  defaultSeconds?: number,
): string {
  const effective =
    seconds != null && seconds > 0 ? seconds : (defaultSeconds ?? 0);
  if (effective <= 0) return "—";
  if (effective < 60) return `~${Math.max(1, Math.round(effective))} Seconds`;
  const minutes = effective / 60;
  if (minutes < 1.5) return "~1 Minute";
  const low = Math.floor(minutes);
  const high = Math.ceil(minutes);
  if (low === high) return `${low} Minutes`;
  return `${low}–${high} Minutes`;
}

export function expectedTimeDescription(seconds: number | null): string {
  return seconds == null
    ? "Default estimate (no run history yet)"
    : "Average of recent successful runs";
}

/** "Generated Reports" card value: X successfully generated of Y configured. */
export function generatedReportsValue(summary: DashboardSummary): string {
  return `${summary.successful_report_count}/${summary.total_enabled_reports}`;
}

export function reportsAvailableDescription(summary: DashboardSummary): string {
  if (summary.generated_report_count > 0) {
    return `${summary.generated_report_count} files ready to preview and download`;
  }
  return "Ready to generate";
}

export function formatReportDuration(seconds: number | null): string {
  if (seconds == null || seconds <= 0) return "~2 min";
  if (seconds < 60) return `~${Math.max(1, Math.round(seconds))} sec`;
  return `~${Math.max(1, Math.round(seconds / 60))} min`;
}
