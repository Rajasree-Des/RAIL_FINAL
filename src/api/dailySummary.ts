import { apiRequest, API_BASE, getCsrfToken } from "@/api/client";

export interface DailySummary {
  summary_id: string;
  run_id: string | null;
  user_id: string | null;
  report_date: string | null;
  status: string;
  text: string;
  source_reports: string[];
  source_row_counts: Record<string, number>;
  missing_reports: string[];
  run_status: string | null;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface DailySummaryListItem {
  summary_id: string;
  run_id: string | null;
  report_date: string | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
  missing_reports: string[];
}

export interface DailySummaryListResponse {
  items: DailySummaryListItem[];
  total: number;
}

export const dailySummaryApi = {
  getForRun(runId: string): Promise<DailySummary> {
    return apiRequest<DailySummary>(`/automation/runs/${runId}/summary`);
  },

  regenerate(runId: string): Promise<DailySummary> {
    return apiRequest<DailySummary>(`/automation/runs/${runId}/summary/regenerate`, {
      method: "POST",
    });
  },

  markCopied(runId: string): Promise<void> {
    return apiRequest<void>(`/automation/runs/${runId}/summary/copied`, {
      method: "POST",
    });
  },

  list(limit = 30, offset = 0): Promise<DailySummaryListResponse> {
    return apiRequest<DailySummaryListResponse>(
      `/summaries?limit=${limit}&offset=${offset}`,
    );
  },

  downloadUrl(summaryId: string): string {
    return `${API_BASE}/summaries/${summaryId}/download`;
  },

  async downloadTxt(summaryId: string, filenameHint?: string): Promise<void> {
    const headers: Record<string, string> = { Accept: "text/plain" };
    const csrf = getCsrfToken();
    if (csrf) headers["X-CSRF-Token"] = csrf;
    const response = await fetch(dailySummaryApi.downloadUrl(summaryId), {
      credentials: "include",
      headers,
    });
    if (!response.ok) {
      throw new Error(`Download failed (${response.status})`);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = /filename\*?=(?:UTF-8''|")?([^\";]+)/i.exec(disposition);
    const filename = filenameHint || (match ? decodeURIComponent(match[1]) : "Daily_Summary.txt");
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  },
};
