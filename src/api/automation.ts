/**
 * Automation orchestration API client
 */

import { apiRequest, API_BASE, AUTOMATION_START_TIMEOUT_MS } from "./client";

export interface AutomationRunSummary {
  id: string;
  profile_id: string;
  profile_name: string;
  status: string;
  trigger_type: string;
  success_count: number;
  failure_count: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface AutomationStatus {
  active_run: AutomationRunSummary | null;
  last_run: AutomationRunSummary | null;
  next_scheduled_at: string | null;
  success_rate: number;
  total_runs: number;
  total_failures: number;
  is_paused: boolean;
}

export interface AutomationLogEntry {
  id: string;
  level: string;
  message: string;
  created_at: string;
}

export interface AutomationProfile {
  id: string;
  name: string;
  slug: string;
  portal_url: string;
  username_masked: string;
  download_folder: string;
  browser: string;
  headless: boolean;
  timeout_ms: number;
  retry_count: number;
  delay_seconds: number;
  report_sequence: { name: string; report_path: string; filters: Record<string, unknown> }[];
  is_enabled: boolean;
}

export interface ReportResult {
  slug: string;
  status: "success" | "partial_success" | "failed" | "skipped";
  dataset_key?: string | null;
  source_csv_path?: string | null;
  source_row_count?: number | null;
  row_count?: number | null;
  ingestion_success?: boolean;
  excel_path?: string | null;
  pdf_path?: string | null;
  pdf_download_url?: string | null;
  excel_download_url?: string | null;
  pdf_preview_url?: string | null;
  error?: string | null;
  processing_success?: boolean;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  extraction_seconds?: number | null;
  processing_seconds?: number | null;
}

export interface AutomationStartResult {
  success: boolean;
  connected: boolean;
  tab_found: boolean;
  url?: string | null;
  title?: string | null;
  error?: string | null;
  error_code?: string | null;
  reports?: ReportResult[];
  stopped_early?: boolean;
  stop_reason?: string | null;
  session_valid?: boolean;
  run_id?: string | null;
  total_duration_seconds?: number | null;
  reports_successful?: number;
  reports_failed?: number;
  download_pdf_all_url?: string | null;
  download_excel_all_url?: string | null;
  report_reached?: boolean;
  report_name?: string | null;
  screenshot_path?: string | null;
  report_generated?: boolean;
  filters_applied?: { field: string; value: string }[];
  row_count?: number | null;
  screenshot_before_path?: string | null;
  screenshot_after_path?: string | null;
  download_success?: boolean;
  download_file_path?: string | null;
  download_file_size?: number | null;
  download_error?: string | null;
  ingestion_success?: boolean;
  ingestion_attempted?: boolean;
  ingestion_source?: string | null;
  ingestion_file_path?: string | null;
  screenshot_before_download_path?: string | null;
  screenshot_after_download_path?: string | null;
  html_extracted?: boolean;
  extracted_data_path?: string | null;
  feedback_extracted?: boolean;
  feedback_csv_path?: string | null;
  pdf_archived?: boolean;
  pdf_archive_path?: string | null;
  pdf_archive_error?: string | null;
  pdf_archive_source?: string | null;
  processing_attempted?: boolean;
  processing_success?: boolean;
  processor_used?: string | null;
  input_row_count?: number | null;
  processed_row_count?: number | null;
  excel_path?: string | null;
  pdf_path?: string | null;
  processing_error?: string | null;
  source_a_path?: string | null;
  source_b_path?: string | null;
  source_a_rows?: number | null;
  source_b_rows?: number | null;
}

export interface AutomationArtifact {
  id: string;
  run_id: string;
  report_slug?: string | null;
  report_name?: string | null;
  file_type: string;
  file_size?: number | null;
  created_at?: string | null;
  status: string;
  preview_url?: string | null;
  download_url?: string | null;
}

export interface AutomationRunDetail {
  run_id: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  success_count: number;
  failure_count: number;
  error?: string | null;
  total_duration_seconds?: number | null;
  reports_successful: number;
  reports_failed: number;
  download_pdf_all_url?: string | null;
  download_excel_all_url?: string | null;
  reports: ReportResult[];
  result?: AutomationStartResult | null;
}

export interface CdpRunSummary {
  run_id: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  success_count: number;
  failure_count: number;
  download_pdf_all_url?: string | null;
  download_excel_all_url?: string | null;
}

export const automationApi = {
  async getStatus(): Promise<AutomationStatus> {
    return apiRequest<AutomationStatus>("/automation/status");
  },

  async getHistory(limit = 20): Promise<{ runs: AutomationRunSummary[]; total: number }> {
    return apiRequest(`/automation/history?limit=${limit}`);
  },

  async getLogs(runId?: string): Promise<{ run_id: string | null; logs: AutomationLogEntry[]; total: number }> {
    const q = runId ? `?run_id=${runId}` : "";
    return apiRequest(`/automation/logs${q}`);
  },

  async run(profileId?: string): Promise<{ run_id: string; status: string; message: string }> {
    return apiRequest("/automation/run", {
      method: "POST",
      body: JSON.stringify({ profile_id: profileId ?? null }),
    });
  },

  async start(options?: {
    report_slugs?: string[];
    async_mode?: boolean;
    date_from?: string;
    date_to?: string;
  }): Promise<AutomationStartResult> {
    return apiRequest<AutomationStartResult>(
      "/automation/start",
      {
        method: "POST",
        body: JSON.stringify({
          report_slugs: options?.report_slugs ?? null,
          async_mode: options?.async_mode ?? false,
          date_from: options?.date_from ?? null,
          date_to: options?.date_to ?? null,
        }),
      },
      false,
      options?.async_mode ? 60_000 : AUTOMATION_START_TIMEOUT_MS,
    );
  },

  async getRun(runId: string): Promise<AutomationRunDetail> {
    return apiRequest<AutomationRunDetail>(`/automation/runs/${encodeURIComponent(runId)}`);
  },

  async getRunArtifacts(runId: string): Promise<AutomationArtifact[]> {
    return apiRequest<AutomationArtifact[]>(
      `/automation/runs/${encodeURIComponent(runId)}/artifacts`,
    );
  },

  async listCdpRuns(limit = 20): Promise<CdpRunSummary[]> {
    return apiRequest<CdpRunSummary[]>(`/automation/cdp-runs?limit=${limit}`);
  },

  artifactPreviewUrl(artifactId: string): string {
    return `${API_BASE}/automation/artifacts/${encodeURIComponent(artifactId)}/preview`;
  },

  withCacheBust(url: string, artifactId?: string | null, runId?: string | null): string {
    const params = new URLSearchParams();
    if (artifactId) params.set("v", artifactId);
    if (runId) params.set("run_id", runId);
    const query = params.toString();
    return query ? `${url}${url.includes("?") ? "&" : "?"}${query}` : url;
  },

  artifactDownloadUrl(artifactId: string): string {
    return `${API_BASE}/automation/artifacts/${encodeURIComponent(artifactId)}/download`;
  },

  downloadPdfAllUrl(runId: string): string {
    return `${API_BASE}/automation/runs/${encodeURIComponent(runId)}/download/pdf/all`;
  },

  downloadExcelAllUrl(runId: string): string {
    return `${API_BASE}/automation/runs/${encodeURIComponent(runId)}/download/excel/all`;
  },

  pdfDownloadUrl(reportKey: string): string {
    return `${API_BASE}/automation/reports/${encodeURIComponent(reportKey)}/pdf`;
  },

  resolveApiUrl(url: string): string {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      return url;
    }
    if (url.startsWith("/api/v1/")) {
      return `${API_BASE}${url.slice("/api/v1".length)}`;
    }
    if (url.startsWith("/")) {
      return `${API_BASE}${url}`;
    }
    return `${API_BASE}/${url}`;
  },

  async fetchPreviewBlobUrl(url: string): Promise<string> {
    const response = await fetch(this.resolveApiUrl(url), {
      method: "GET",
      credentials: "include",
    });
    if (!response.ok) {
      throw new Error(`Preview failed: ${response.status}`);
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  },

  parseFilenameFromDisposition(header: string | null, fallback: string): string {
    if (!header) return fallback;
    const utfMatch = /filename\*=UTF-8''([^;]+)/i.exec(header);
    if (utfMatch?.[1]) {
      try {
        return decodeURIComponent(utfMatch[1].trim());
      } catch {
        return utfMatch[1].trim();
      }
    }
    const plainMatch = /filename="?([^";]+)"?/i.exec(header);
    if (plainMatch?.[1]) return plainMatch[1].trim();
    return fallback;
  },

  async downloadBlob(
    url: string,
    fallbackFilename = "download.bin",
  ): Promise<{ blob: Blob; filename: string }> {
    const response = await fetch(this.resolveApiUrl(url), {
      method: "GET",
      credentials: "include",
    });
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`);
    }
    const blob = await response.blob();
    const filename = this.parseFilenameFromDisposition(
      response.headers.get("Content-Disposition"),
      fallbackFilename,
    );
    return { blob, filename };
  },

  async downloadPdf(reportKey: string): Promise<{ blob: Blob; filename: string }> {
    return this.downloadBlob(this.pdfDownloadUrl(reportKey), `${reportKey}.pdf`);
  },

  async stop(runId?: string): Promise<{
    success: boolean;
    status: string;
    message: string;
    run_id?: string;
  }> {
    if (runId) {
      return apiRequest(`/automation/runs/${encodeURIComponent(runId)}/stop`, {
        method: "POST",
      });
    }
    return apiRequest("/automation/stop", { method: "POST" });
  },

  async pause(runId?: string): Promise<{
    success: boolean;
    status: string;
    message: string;
    run_id?: string;
  }> {
    if (runId) {
      return apiRequest(`/automation/runs/${encodeURIComponent(runId)}/pause`, {
        method: "POST",
      });
    }
    return apiRequest("/automation/pause", { method: "POST" });
  },

  async resume(runId?: string): Promise<{
    success: boolean;
    status: string;
    message: string;
    run_id?: string;
  }> {
    if (runId) {
      return apiRequest(`/automation/runs/${encodeURIComponent(runId)}/resume`, {
        method: "POST",
      });
    }
    return apiRequest("/automation/resume", { method: "POST" });
  },

  async listProfiles(): Promise<{ profiles: AutomationProfile[]; total: number }> {
    return apiRequest("/automation/profiles");
  },
};
