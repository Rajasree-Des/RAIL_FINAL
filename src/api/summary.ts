/**
 * AI Summary Generator API client
 */

import { apiRequest } from "./client";
import { buildQueryString } from "./query";

export type SummaryType =
  | "executive"
  | "whatsapp"
  | "email"
  | "daily_highlights"
  | "key_observations";

export interface ReportMetadata {
  report_name?: string;
  report_period?: string;
  division?: string | null;
  included_reports?: string[];
  generated_by?: string | null;
}

export interface ReportStatistics {
  total_complaints: number;
  resolved_complaints: number;
  pending_complaints: number;
  resolution_rate: number;
  unsatisfactory_count: number;
  unsatisfactory_rate: number;
  top_complaint_types: { name: string; count: number; percentage: number }[];
  top_divisions: { name: string; count: number; percentage: number }[];
  top_trains: { name: string; count: number; percentage: number }[];
  bottom_trains: { name: string; count: number; percentage: number }[];
  scr_train_count: number;
  daily_highlights: string[];
  key_observations: string[];
  report_period: string;
  generated_at: string;
}

export interface GeneratedSummaryResult {
  id: string;
  summary_type: string;
  content: string;
  statistics: ReportStatistics;
  prompt_template_id: string | null;
  generation_time_ms: number;
  model_used: string | null;
  created_at: string;
}

export interface PromptTemplate {
  id: string;
  name: string;
  slug: string;
  summary_type: SummaryType;
  description: string | null;
  system_prompt: string;
  user_prompt_template: string;
  output_format: "markdown" | "plain_text" | "bullets";
  max_tokens: number;
  temperature: number;
  is_enabled: boolean;
  is_default: boolean;
  template_id: string | null;
  is_deleted: boolean;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface PromptTemplateListItem {
  id: string;
  name: string;
  slug: string;
  summary_type: SummaryType;
  description: string | null;
  is_enabled: boolean;
  is_default: boolean;
  max_tokens: number;
  temperature: number;
  created_at: string;
  updated_at: string;
}

export interface GenerateSummaryRequest {
  prompt_template_id?: string;
  summary_type?: SummaryType;
  dataset: Record<string, unknown>[];
  metadata?: ReportMetadata;
  column_mapping?: Record<string, string>;
  regenerate?: boolean;
}

export interface CreatePromptTemplateRequest {
  name: string;
  slug: string;
  summary_type: SummaryType;
  description?: string;
  system_prompt: string;
  user_prompt_template: string;
  output_format?: "markdown" | "plain_text" | "bullets";
  max_tokens?: number;
  temperature?: number;
  is_enabled?: boolean;
  is_default?: boolean;
  template_id?: string;
}

export interface UpdatePromptTemplateRequest {
  name?: string;
  slug?: string;
  summary_type?: SummaryType;
  description?: string;
  system_prompt?: string;
  user_prompt_template?: string;
  output_format?: "markdown" | "plain_text" | "bullets";
  max_tokens?: number;
  temperature?: number;
  is_enabled?: boolean;
  is_default?: boolean;
  template_id?: string;
}

export interface TestPromptResult {
  content: string;
  statistics: ReportStatistics;
  rendered_user_prompt: string;
  generation_time_ms: number;
  model_used: string | null;
}

export const SUMMARY_TYPE_LABELS: Record<SummaryType, string> = {
  executive: "Executive Summary",
  whatsapp: "WhatsApp Summary",
  email: "Official Email",
  daily_highlights: "Daily Highlights",
  key_observations: "Key Observations",
};

export const summaryApi = {
  async generate(data: GenerateSummaryRequest): Promise<GeneratedSummaryResult> {
    return apiRequest<GeneratedSummaryResult>("/summary/generate", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async get(summaryId: string): Promise<GeneratedSummaryResult> {
    return apiRequest<GeneratedSummaryResult>(`/summary/${summaryId}`);
  },

  async listTemplates(params?: {
    summary_type?: string;
    is_enabled?: boolean;
  }): Promise<{ templates: PromptTemplateListItem[]; total: number }> {
    return apiRequest(`/summary/templates${buildQueryString(params ?? {})}`);
  },

  async getTemplate(templateId: string): Promise<PromptTemplate> {
    return apiRequest<PromptTemplate>(`/summary/templates/${templateId}`);
  },

  async createTemplate(data: CreatePromptTemplateRequest): Promise<PromptTemplate> {
    return apiRequest<PromptTemplate>("/summary/templates", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updateTemplate(
    templateId: string,
    data: UpdatePromptTemplateRequest,
  ): Promise<PromptTemplate> {
    return apiRequest<PromptTemplate>(`/summary/templates/${templateId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  async deleteTemplate(
    templateId: string,
  ): Promise<{ success: boolean; message: string }> {
    return apiRequest(`/summary/templates/${templateId}`, {
      method: "DELETE",
    });
  },

  async toggleTemplate(
    templateId: string,
  ): Promise<{ id: string; is_enabled: boolean }> {
    return apiRequest(`/summary/templates/${templateId}/toggle`, {
      method: "PATCH",
    });
  },

  async duplicateTemplate(
    templateId: string,
    newName: string,
    newSlug?: string,
  ): Promise<PromptTemplate> {
    return apiRequest(
      `/summary/templates/${templateId}/duplicate${buildQueryString({
        new_name: newName,
        new_slug: newSlug,
      })}`,
      { method: "POST" },
    );
  },

  async testTemplate(
    templateId: string,
    data: {
      sample_dataset: Record<string, unknown>[];
      sample_metadata?: ReportMetadata;
      column_mapping?: Record<string, string>;
    },
  ): Promise<TestPromptResult> {
    return apiRequest(`/summary/templates/${templateId}/test`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};
