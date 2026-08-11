/**
 * Manual report generation API (Report Configuration pages)
 */

import { apiRequest, API_TIMEOUT_MS, PREVIEW_TIMEOUT_MS } from "./client";
import { automationApi } from "./automation";

export type ManualUiStatus =
  | "Waiting"
  | "Extracting"
  | "Ingesting"
  | "Processing"
  | "Generating Excel/PDF"
  | "Completed"
  | "Failed";

export interface ManualGenerateRequest {
  report_slug?: string;
  date_from?: string;
  date_to?: string;
  selected_column_ids: string[];
  column_order: string[];
  export_format: "xlsx" | "pdf" | "csv";
  requested_formats?: Array<"xlsx" | "pdf">;
  configuration_source?: "manual_snapshot";
  force_fresh_extraction?: boolean;
  config_overrides?: Record<string, unknown>;
  filter_conditions?: Array<Record<string, unknown>>;
  sections?: Record<string, { selected_column_ids: string[] }>;
}

export interface ManualGenerateResponse {
  run_id: string;
  report_slug: string;
  report_date: string;
  status: ManualUiStatus;
  message?: string;
}

export interface ManualRunStatus {
  run_id: string;
  report_slug: string;
  report_date: string | null;
  status: ManualUiStatus;
  run_status: string;
  source_row_count: number | null;
  processed_row_count: number | null;
  row_counts: Record<string, number>;
  extraction_success: boolean;
  ingestion_success: boolean;
  processing_success: boolean;
  artifact_id: string | null;
  preview_url: string | null;
  download_url: string | null;
  export_format: string;
  visible_columns: string[];
  preview_rows: Record<string, string | number>[];
  output_filename: string | null;
  output_file_size: number | null;
  generated_at: string | null;
  error: string | null;
  excel_artifact_id?: string | null;
  excel_download_url?: string | null;
  excel_filename?: string | null;
  excel_file_size?: number | null;
  pdf_artifact_id?: string | null;
  pdf_download_url?: string | null;
  pdf_preview_url?: string | null;
  pdf_filename?: string | null;
  pdf_file_size?: number | null;
}

export interface SavedReportConfig {
  report_slug?: string;
  available_columns?: OutputColumnCatalogResponse["columns"];
  selected_column_ids: string[];
  column_order: string[];
  default_column_ids?: string[];
  /** User-saved defaults for Output Column Filters (persisted in report config). */
  default_selected_column_ids?: string[];
  /** Per-section defaults for comprehensive reports 10–13. */
  default_sections?: Record<string, { selected_column_ids: string[] }>;
  has_saved_configuration?: boolean;
  export_format: "xlsx" | "pdf" | "csv";
  config_overrides?: Record<string, unknown>;
  filter_conditions?: Array<Record<string, unknown>>;
  sections?: Record<string, { selected_column_ids: string[] }>;
  date_from?: string;
  date_to?: string;
}

export interface OutputColumnCatalogResponse {
  report_slug: string;
  columns: Array<{
    id: string;
    label: string;
    required: boolean;
    default_visible: boolean;
    group?: string;
    group_title?: string;
  }>;
  default_column_ids: string[];
}

export interface OutputPreviewRequest {
  selected_column_ids: string[];
  column_order: string[];
}

export interface SectionPreview {
  title: string;
  headers: string[];
  rows: Record<string, string | number>[];
  empty: boolean;
}

export interface OutputPreviewResponse {
  available: boolean;
  message?: string | null;
  report_slug?: string | null;
  visible_columns: string[];
  preview_rows: Record<string, string | number>[];
  sections?: SectionPreview[];
  selected_count: number;
  selected_column_ids?: string[];
  column_order?: string[];
  preview_version?: number;
}

export const PAGE_ID_TO_SLUG: Record<string, string> = {
  zone: "report1",
  merging: "report1",
  report1: "report1",
  division: "division",
  report2: "division",
  "train-no": "train-no",
  report3: "train-no",
  types: "types",
  report4: "types",
  "scr-train": "scr-train",
  report5: "scr-train",
  "scr-station": "scr-station",
  report6_station: "scr-station",
  report9: "report9",
  "comprehensive-10-13": "comprehensive-10-13",
  report14: "report14",
  report18: "report18",
  "bottom-report": "bottom-report",
};

export function resolveReportSlug(pageId: string): string {
  return PAGE_ID_TO_SLUG[pageId] ?? pageId;
}

export const reportsApi = {
  async generate(
    pageId: string,
    body: ManualGenerateRequest,
  ): Promise<ManualGenerateResponse> {
    const slug = resolveReportSlug(pageId);
    return apiRequest<ManualGenerateResponse>(
      `/reports/${encodeURIComponent(slug)}/generate`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    );
  },

  async getRunStatus(runId: string, reportSlug?: string): Promise<ManualRunStatus> {
    const query = reportSlug
      ? `?report_slug=${encodeURIComponent(reportSlug)}`
      : "";
    const status = await apiRequest<ManualRunStatus>(
      `/reports/runs/${encodeURIComponent(runId)}${query}`,
    );
    return status;
  },

  async saveConfig(pageId: string, body: SavedReportConfig): Promise<void> {
    const slug = resolveReportSlug(pageId);
    await apiRequest(`/reports/${encodeURIComponent(slug)}/config`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  async loadConfig(pageId: string): Promise<SavedReportConfig | null> {
    const slug = resolveReportSlug(pageId);
    try {
      return await apiRequest<SavedReportConfig>(
        `/reports/${encodeURIComponent(slug)}/config`,
      );
    } catch {
      return null;
    }
  },

  async getOutputColumns(pageId: string): Promise<OutputColumnCatalogResponse> {
    const slug = resolveReportSlug(pageId);
    return apiRequest<OutputColumnCatalogResponse>(
      `/reports/${encodeURIComponent(slug)}/output-columns`,
    );
  },

  async outputPreview(
    pageId: string,
    body: OutputPreviewRequest,
    options?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<OutputPreviewResponse> {
    const slug = resolveReportSlug(pageId);
    return apiRequest<OutputPreviewResponse>(
      `/reports/${encodeURIComponent(slug)}/preview`,
      {
        method: "POST",
        body: JSON.stringify(body),
        signal: options?.signal,
      },
      false,
      options?.timeoutMs ?? API_TIMEOUT_MS,
    );
  },

  async downloadCurrentRun(
    status: ManualRunStatus,
  ): Promise<{ blob: Blob; filename: string }> {
    if (!status.download_url || !status.artifact_id) {
      throw new Error("No downloadable artifact for this run");
    }
    const url = automationApi.withCacheBust(
      status.download_url,
      status.artifact_id,
      status.run_id,
    );
    const fallback =
      status.output_filename ||
      `${status.report_slug}.${status.export_format === "pdf" ? "pdf" : "xlsx"}`;
    return automationApi.downloadBlob(url, fallback);
  },

  async downloadManualExcel(
    status: ManualRunStatus,
  ): Promise<{ blob: Blob; filename: string }> {
    if (!status.excel_download_url) {
      throw new Error("No Excel artifact for this run");
    }
    const url = automationApi.withCacheBust(
      status.excel_download_url,
      status.excel_artifact_id,
      status.run_id,
    );
    const fallback =
      status.excel_filename || `${status.report_slug}.xlsx`;
    return automationApi.downloadBlob(url, fallback);
  },

  async downloadManualPdf(
    status: ManualRunStatus,
  ): Promise<{ blob: Blob; filename: string }> {
    if (!status.pdf_download_url) {
      throw new Error("No PDF artifact for this run");
    }
    const url = automationApi.withCacheBust(
      status.pdf_download_url,
      status.pdf_artifact_id,
      status.run_id,
    );
    const fallback = status.pdf_filename || `${status.report_slug}.pdf`;
    return automationApi.downloadBlob(url, fallback);
  },

  previewManualPdf(status: ManualRunStatus): string {
    if (!status.pdf_preview_url) {
      throw new Error("No PDF preview for this run");
    }
    return automationApi.withCacheBust(
      status.pdf_preview_url,
      status.pdf_artifact_id,
      status.run_id,
    );
  },
};

export function isTerminalManualStatus(status: ManualUiStatus): boolean {
  return status === "Completed" || status === "Failed";
}

export function usesDualManualArtifacts(reportSlug: string): boolean {
  return (
    reportSlug === "report1" ||
    reportSlug === "division" ||
    reportSlug === "scr-train" ||
    reportSlug === "scr-station" ||
    reportSlug === "train-no" ||
    reportSlug === "types" ||
    reportSlug === "report9" ||
    reportSlug === "comprehensive-10-13" ||
    reportSlug === "report14" ||
    reportSlug === "report18" ||
    reportSlug === "bottom-report"
  );
}

function manualRunSucceeded(status: ManualRunStatus): boolean {
  return (
    status.status === "Completed" &&
    status.extraction_success &&
    status.ingestion_success &&
    status.processing_success
  );
}

export function canDownloadManualStatus(status: ManualRunStatus): boolean {
  if (usesDualManualArtifacts(status.report_slug)) {
    return canDownloadExcel(status) || canDownloadPdf(status);
  }
  return (
    manualRunSucceeded(status) &&
    Boolean(status.artifact_id) &&
    Boolean(status.download_url)
  );
}

export function canDownloadExcel(status: ManualRunStatus): boolean {
  return manualRunSucceeded(status) && Boolean(status.excel_download_url);
}

export function canDownloadPdf(status: ManualRunStatus): boolean {
  return manualRunSucceeded(status) && Boolean(status.pdf_download_url);
}

export function canPreviewPdf(status: ManualRunStatus): boolean {
  return manualRunSucceeded(status) && Boolean(status.pdf_preview_url);
}

export function formatFileSize(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
