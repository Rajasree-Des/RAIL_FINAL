/**
 * Centralized application settings API client
 */

import { apiRequest } from "./client";
import { buildQueryString } from "./query";

export type SettingValueType =
  | "string"
  | "number"
  | "boolean"
  | "enum"
  | "multiselect"
  | "json";

export interface SettingOption {
  label: string;
  value: string | number | boolean;
}

export interface SettingItem {
  id: string;
  category: string;
  key: string;
  label: string;
  description: string | null;
  value_type: SettingValueType;
  value: unknown;
  default_value: unknown;
  validation: Record<string, unknown> | null;
  options: SettingOption[] | null;
  sort_order: number;
  is_editable: boolean;
  is_modified: boolean;
}

export interface SettingCategory {
  slug: string;
  label: string;
  description: string | null;
  settings: SettingItem[];
}

export interface SettingsResponse {
  version: string;
  categories: SettingCategory[];
  total: number;
}

export interface SettingUpdateItem {
  category: string;
  key: string;
  value: unknown;
}

export interface SettingsExportPayload {
  version: string;
  exported_at: string;
  settings: Record<string, unknown>;
}

export const SETTINGS_CATEGORY_META: Record<
  string,
  { label: string; description: string }
> = {
  general: {
    label: "General",
    description: "Organization, time zone, and display formats",
  },
  notifications: {
    label: "Notifications",
    description: "Report completion and failure alerts",
  },
  account: {
    label: "Account",
    description: "Password and session preferences",
  },
  system: {
    label: "System",
    description: "Live status and maintenance",
  },
};

export const settingsApi = {
  async get(params?: {
    category?: string;
    search?: string;
  }): Promise<SettingsResponse> {
    return apiRequest<SettingsResponse>(`/settings${buildQueryString(params ?? {})}`);
  },

  async update(settings: SettingUpdateItem[]): Promise<{
    updated: number;
    settings: SettingItem[];
  }> {
    return apiRequest("/settings", {
      method: "PUT",
      body: JSON.stringify({ settings }),
    });
  },

  async resetCategory(category: string): Promise<{
    success: boolean;
    reset_count: number;
    category: string;
  }> {
    return apiRequest(`/settings/reset/${category}`, {
      method: "POST",
    });
  },

  async export(): Promise<SettingsExportPayload> {
    return apiRequest<SettingsExportPayload>("/settings/export");
  },

  async import(
    payload: { version?: string; settings: Record<string, unknown>; merge?: boolean },
  ): Promise<{ imported: number; skipped: number; errors: string[] }> {
    return apiRequest("/settings/import", {
      method: "POST",
      body: JSON.stringify({
        version: payload.version ?? "1.0",
        settings: payload.settings,
        merge: payload.merge ?? true,
      }),
    });
  },
};
