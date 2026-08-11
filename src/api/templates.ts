import { apiRequest } from "./client";

// =============================================================================
// Types
// =============================================================================

export interface InputConfig {
  id?: string;
  accepted_file_types: string[];
  required_sheets: string[] | null;
  header_row: number;
  validation_rules: Record<string, unknown>;
}

export interface ColumnMapping {
  id?: string;
  source_column: string;
  internal_field: string;
  output_column: string;
  data_type: "text" | "number" | "date" | "boolean";
  is_required: boolean;
  default_value: string | null;
  transform: "none" | "uppercase" | "lowercase" | "trim";
  sort_order: number;
}

export interface SortingRule {
  id?: string;
  column_name: string;
  direction: "asc" | "desc";
  priority: number;
}

export interface FilteringRule {
  id?: string;
  column_name: string;
  operator:
    | "equals"
    | "not_equals"
    | "contains"
    | "gt"
    | "lt"
    | "gte"
    | "lte"
    | "in"
    | "not_in"
    | "is_null"
    | "is_not_null";
  value: string | null;
  value_type: "string" | "number" | "date" | "boolean";
  logic_group: "AND" | "OR";
}

export interface RowRule {
  id?: string;
  rule_type: "none" | "top_n" | "bottom_n" | "custom";
  limit_value: number | null;
  limit_column: string | null;
  custom_expression: string | null;
}

export interface HighlightRule {
  id?: string;
  column_name: string;
  condition_type: "equals" | "gt" | "lt" | "gte" | "lte" | "contains" | "between";
  condition_value: string | null;
  highlight_color: string;
  text_color: string | null;
  is_bold: boolean;
  priority: number;
}

export interface OutputConfig {
  id?: string;
  excel_enabled: boolean;
  excel_config: Record<string, unknown>;
  pdf_enabled: boolean;
  pdf_config: Record<string, unknown>;
  ai_summary_enabled: boolean;
  ai_config: Record<string, unknown>;
  whatsapp_enabled: boolean;
  whatsapp_config: Record<string, unknown>;
  email_enabled: boolean;
  email_config: Record<string, unknown>;
}

export interface Template {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  source_report_id: string | null;
  is_enabled: boolean;
  version: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  updated_by: string | null;
  input_config: InputConfig | null;
  column_mappings: ColumnMapping[];
  sorting_rules: SortingRule[];
  filtering_rules: FilteringRule[];
  row_rule: RowRule | null;
  highlight_rules: HighlightRule[];
  output_config: OutputConfig | null;
}

export interface TemplateListItem {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  source_report_id: string | null;
  is_enabled: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  has_input_config: boolean;
  has_output_config: boolean;
  column_count: number;
}

export interface TemplateListResponse {
  templates: TemplateListItem[];
  total: number;
}

export interface CreateTemplateRequest {
  name: string;
  slug?: string;
  description?: string;
  source_report_id?: string;
  is_enabled?: boolean;
  metadata?: Record<string, unknown>;
  input_config?: Omit<InputConfig, "id">;
  column_mappings?: Omit<ColumnMapping, "id">[];
  sorting_rules?: Omit<SortingRule, "id">[];
  filtering_rules?: Omit<FilteringRule, "id">[];
  row_rule?: Omit<RowRule, "id">;
  highlight_rules?: Omit<HighlightRule, "id">[];
  output_config?: Omit<OutputConfig, "id">;
}

export interface UpdateTemplateRequest {
  name?: string;
  slug?: string;
  description?: string;
  source_report_id?: string;
  is_enabled?: boolean;
  metadata?: Record<string, unknown>;
  input_config?: Omit<InputConfig, "id">;
  column_mappings?: Omit<ColumnMapping, "id">[];
  sorting_rules?: Omit<SortingRule, "id">[];
  filtering_rules?: Omit<FilteringRule, "id">[];
  row_rule?: Omit<RowRule, "id">;
  highlight_rules?: Omit<HighlightRule, "id">[];
  output_config?: Omit<OutputConfig, "id">;
}

export interface ValidationResult {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface ToggleResponse {
  id: string;
  is_enabled: boolean;
  message: string;
}

export interface DeleteResponse {
  success: boolean;
  message: string;
}

// =============================================================================
// API Functions
// =============================================================================

export const templatesApi = {
  async list(enabledOnly = false): Promise<TemplateListResponse> {
    const params = enabledOnly ? "?enabled_only=true" : "";
    return apiRequest<TemplateListResponse>(`/admin/templates${params}`);
  },

  async get(id: string): Promise<Template> {
    return apiRequest<Template>(`/admin/templates/${id}`);
  },

  async create(data: CreateTemplateRequest): Promise<Template> {
    return apiRequest<Template>("/admin/templates", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async update(id: string, data: UpdateTemplateRequest): Promise<Template> {
    return apiRequest<Template>(`/admin/templates/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  async delete(id: string): Promise<DeleteResponse> {
    return apiRequest<DeleteResponse>(`/admin/templates/${id}`, {
      method: "DELETE",
    });
  },

  async duplicate(id: string, newName: string): Promise<Template> {
    return apiRequest<Template>(`/admin/templates/${id}/duplicate`, {
      method: "POST",
      body: JSON.stringify({ new_name: newName }),
    });
  },

  async toggle(id: string): Promise<ToggleResponse> {
    return apiRequest<ToggleResponse>(`/admin/templates/${id}/toggle`, {
      method: "PATCH",
    });
  },

  async test(id: string): Promise<ValidationResult> {
    return apiRequest<ValidationResult>(`/admin/templates/${id}/test`, {
      method: "POST",
    });
  },
};
