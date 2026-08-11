import { apiRequest } from "./client";
import type { ActivityEntry } from "./activity";

/** Canonical status vocabulary shared with the backend. */
export type DashboardStatus =
  | "ready"
  | "pending"
  | "running"
  | "processing"
  | "paused"
  | "success"
  | "partial_success"
  | "failed"
  | "stopped"
  | "skipped";

export interface DashboardReportStatus {
  slug: string;
  name: string;
  status: DashboardStatus;
  error: string | null;
  last_duration_seconds: number | null;
}

export interface DashboardSummary {
  current_status: DashboardStatus;
  active_run_id: string | null;
  last_run_id: string | null;
  last_run_status: DashboardStatus | null;
  last_generated_at: string | null;
  successful_report_count: number;
  failed_report_count: number;
  generated_report_count: number;
  total_enabled_reports: number;
  estimated_duration_seconds: number | null;
  default_expected_duration_seconds: number;
  reports: DashboardReportStatus[];
  recent_activity: ActivityEntry[];
}

export interface AnalyticsTotals {
  complaints_received: number;
  feedback_received: number;
  complaints_resolved: number;
  resolution_rate: number;
}

export interface ZoneRow {
  rank: number;
  zone: string;
  complaints: number;
  feedback: number;
  resolution_pct: number | null;
}

export interface DivisionRow {
  rank: number;
  division: string;
  complaints: number;
  feedback: number;
  resolution_pct: number | null;
}

export interface TrainRow {
  rank: number;
  train_no: string;
  train_name: string;
  complaints: number;
  resolution_pct: number | null;
}

export interface ScrEntityRow {
  name: string;
  label: string | null;
  complaints: number;
  complaint_types: string[];
  resolution_pct: number | null;
}

export interface ComplaintTypeRow {
  type_name: string;
  complaints: number;
  percentage: number;
}

export interface NameCount {
  name: string;
  count: number;
}

export interface FeedbackDistribution {
  total: number;
  excellent: number;
  satisfactory: number;
  unsatisfactory: number;
}

export interface ReportFileMeta {
  file_type: string;
  file_size_bytes: number | null;
  download_url: string | null;
  preview_url: string | null;
}

export interface ReportCardInfo {
  slug: string;
  name: string;
  status: DashboardStatus;
  generated_at: string | null;
  duration_seconds: number | null;
  sections_total?: number | null;
  row_count?: number | null;
  files: ReportFileMeta[];
}

export interface DashboardAnalytics {
  has_data: boolean;
  run_id: string | null;
  generated_at: string | null;
  totals: AnalyticsTotals | null;
  zones: ZoneRow[];
  divisions: DivisionRow[];
  trains: TrainRow[];
  scr_trains: ScrEntityRow[];
  scr_stations: ScrEntityRow[];
  complaint_types: ComplaintTypeRow[];
  feedback_distribution: FeedbackDistribution | null;
  top_causes: NameCount[];
  complaints_by_report: NameCount[];
  report_cards: ReportCardInfo[];
}

/** Actions that change what the dashboards display. */
export function isDashboardRelevant(action: string): boolean {
  return (
    action.startsWith("AUTOMATION_") ||
    action.startsWith("REPORT_") ||
    action.endsWith("_GENERATED") ||
    action.endsWith("_DOWNLOADED")
  );
}

export const dashboardApi = {
  summary(): Promise<DashboardSummary> {
    return apiRequest<DashboardSummary>("/dashboard/summary");
  },
  analytics(): Promise<DashboardAnalytics> {
    return apiRequest<DashboardAnalytics>("/dashboard/analytics");
  },
};
