/**
 * System info and maintenance API client (admin only).
 */

import { API_BASE, ApiError } from "./client";

export interface SystemComponentStatus {
  ok: boolean;
  detail: string | null;
}

export interface SystemInfo {
  app_version: string;
  environment: string;
  backend: SystemComponentStatus;
  database: SystemComponentStatus;
  database_type: string;
  cdp: SystemComponentStatus;
  automation_status: string;
  active_run_id: string | null;
  last_successful_run_at: string | null;
  last_failed_run_at: string | null;
  storage_usage_bytes: number;
}

export interface ClearCacheResult {
  success: boolean;
  cleared: string[];
  files_removed: number;
  directories_removed: number;
  bytes_freed: number;
  skipped_locked: number;
  partial: boolean;
}

function parseFilenameFromDisposition(header: string | null, fallback: string): string {
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
}

export const systemApi = {
  async info(): Promise<SystemInfo> {
    const { apiRequest } = await import("./client");
    return apiRequest<SystemInfo>("/system/info");
  },

  async exportLogs(): Promise<{ blob: Blob; filename: string }> {
    const response = await fetch(`${API_BASE}/system/export-logs`, {
      method: "GET",
      credentials: "include",
    });
    if (!response.ok) {
      let message = `Export failed (${response.status})`;
      try {
        const errorData = await response.json();
        const detail = errorData.detail;
        if (typeof detail === "string") {
          message = detail;
        } else if (typeof detail?.message === "string") {
          message = detail.message;
        }
      } catch {
        const text = await response.text();
        if (text) message = text;
      }
      throw new ApiError(message, response.status);
    }
    const blob = await response.blob();
    const filename = parseFilenameFromDisposition(
      response.headers.get("Content-Disposition"),
      "RailMadad_Administrative_Logs.pdf",
    );
    return { blob, filename };
  },

  async clearCache(): Promise<ClearCacheResult> {
    const { apiRequest } = await import("./client");
    return apiRequest<ClearCacheResult>("/system/clear-cache", { method: "POST" });
  },
};
