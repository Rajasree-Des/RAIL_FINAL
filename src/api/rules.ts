/**
 * Business Rules Engine API client
 */

import { apiRequest } from "./client";
import { buildQueryString } from "./query";

// =============================================================================
// Types
// =============================================================================

export type RuleCategory =
  | "column"
  | "conditional"
  | "sorting"
  | "filter"
  | "top"
  | "highlight"
  | "calculation"
  | "merge";

export type ConditionOperator =
  | "equals"
  | "not_equals"
  | "contains"
  | "not_contains"
  | "starts_with"
  | "ends_with"
  | "gt"
  | "lt"
  | "gte"
  | "lte"
  | "in"
  | "not_in"
  | "is_null"
  | "is_not_null"
  | "between"
  | "regex";

export interface Condition {
  field: string;
  operator: ConditionOperator;
  value?: unknown;
  value_type?: "string" | "number" | "date" | "boolean";
}

export interface ConditionGroup {
  logic: "AND" | "OR";
  conditions: Condition[];
  nested?: ConditionGroup[];
}

export interface StyleConfig {
  background_color?: string;
  text_color?: string;
  bold?: boolean;
  italic?: boolean;
  border?: "none" | "thin" | "medium" | "thick";
}

export interface Rule {
  id: string;
  name: string;
  description?: string;
  template_id?: string;
  category: RuleCategory;
  rule_type: string;
  config: Record<string, unknown>;
  priority: number;
  group_id?: string;
  is_enabled: boolean;
  is_global: boolean;
  conditions?: ConditionGroup;
  is_deleted: boolean;
  created_by?: string;
  updated_by?: string;
  created_at: string;
  updated_at: string;
}

export interface RuleListItem {
  id: string;
  name: string;
  description?: string;
  template_id?: string;
  category: string;
  rule_type: string;
  priority: number;
  group_id?: string;
  is_enabled: boolean;
  is_global: boolean;
  created_at: string;
  updated_at: string;
}

export interface RuleListResponse {
  rules: RuleListItem[];
  total: number;
}

export interface CreateRuleRequest {
  name: string;
  description?: string;
  template_id?: string;
  category: RuleCategory;
  rule_type: string;
  config: Record<string, unknown>;
  priority?: number;
  group_id?: string;
  is_enabled?: boolean;
  is_global?: boolean;
  conditions?: ConditionGroup;
}

export interface UpdateRuleRequest {
  name?: string;
  description?: string;
  template_id?: string;
  category?: RuleCategory;
  rule_type?: string;
  config?: Record<string, unknown>;
  priority?: number;
  group_id?: string;
  is_enabled?: boolean;
  is_global?: boolean;
  conditions?: ConditionGroup;
}

export interface RuleTypeInfo {
  type: string;
  name: string;
  description: string;
  config_schema: Record<string, unknown>;
}

export interface CategoryInfo {
  category: string;
  name: string;
  description: string;
  rule_types: RuleTypeInfo[];
}

export interface FunctionInfo {
  name: string;
  description: string;
  signature: string;
  examples: string[];
}

export interface ValidationResult {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface HighlightInfo {
  row: number;
  column: string;
  style: StyleConfig;
}

export interface TestResult {
  success: boolean;
  output_data: Record<string, unknown>[];
  row_count: number;
  column_count: number;
  execution_time_ms: number;
  errors: string[];
  warnings: string[];
}

export interface ExecuteResult {
  success: boolean;
  output_data: Record<string, unknown>[];
  highlights: HighlightInfo[];
  row_count: number;
  column_count: number;
  execution_time_ms: number;
  rules_executed: number;
  execution_log: string[];
  errors: string[];
  warnings: string[];
}

// =============================================================================
// API Functions
// =============================================================================

export const rulesApi = {
  /**
   * List all rules with optional filters
   */
  async list(params?: {
    template_id?: string;
    category?: string;
    is_enabled?: boolean;
  }): Promise<RuleListResponse> {
    return apiRequest<RuleListResponse>(`/rules${buildQueryString(params ?? {})}`);
  },

  /**
   * Get a single rule by ID
   */
  async get(ruleId: string): Promise<Rule> {
    return apiRequest<Rule>(`/rules/${ruleId}`);
  },

  /**
   * Get rules for a specific template
   */
  async getForTemplate(templateId: string): Promise<RuleListItem[]> {
    return apiRequest<RuleListItem[]>(`/rules/templates/${templateId}`);
  },

  /**
   * Create a new rule
   */
  async create(data: CreateRuleRequest): Promise<Rule> {
    return apiRequest<Rule>("/rules", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /**
   * Update an existing rule
   */
  async update(ruleId: string, data: UpdateRuleRequest): Promise<Rule> {
    return apiRequest<Rule>(`/rules/${ruleId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  /**
   * Delete a rule
   */
  async delete(ruleId: string): Promise<{ success: boolean; message: string }> {
    return apiRequest<{ success: boolean; message: string }>(
      `/rules/${ruleId}`,
      {
        method: "DELETE",
      }
    );
  },

  /**
   * Toggle rule enabled status
   */
  async toggle(ruleId: string): Promise<Rule> {
    return apiRequest<Rule>(`/rules/${ruleId}/toggle`, {
      method: "PATCH",
    });
  },

  /**
   * Duplicate a rule
   */
  async duplicate(ruleId: string, newName: string): Promise<Rule> {
    return apiRequest<Rule>(
      `/rules/${ruleId}/duplicate?new_name=${encodeURIComponent(newName)}`,
      {
        method: "POST",
      }
    );
  },

  /**
   * Get available rule categories and types
   */
  async getCategories(): Promise<CategoryInfo[]> {
    return apiRequest<CategoryInfo[]>("/rules/categories");
  },

  /**
   * Get available expression functions
   */
  async getFunctions(): Promise<FunctionInfo[]> {
    return apiRequest<FunctionInfo[]>("/rules/functions");
  },

  /**
   * Validate a rule configuration
   */
  async validate(
    category: RuleCategory,
    ruleType: string,
    config: Record<string, unknown>
  ): Promise<ValidationResult> {
    return apiRequest<ValidationResult>("/rules/validate", {
      method: "POST",
      body: JSON.stringify({
        category,
        rule_type: ruleType,
        config,
      }),
    });
  },

  /**
   * Test a rule against sample data
   */
  async test(params: {
    rule_id?: string;
    rule_config?: CreateRuleRequest;
    sample_data: Record<string, unknown>[];
  }): Promise<TestResult> {
    return apiRequest<TestResult>("/rules/test", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  /**
   * Execute all rules for a template
   */
  async execute(params: {
    template_id: string;
    data: Record<string, unknown>[];
    variables?: Record<string, unknown>;
  }): Promise<ExecuteResult> {
    return apiRequest<ExecuteResult>("/rules/execute", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  /**
   * Reorder rules (update priorities)
   */
  async reorder(
    rulePriorities: { id: string; priority: number }[]
  ): Promise<{ success: boolean; updated_count: number }> {
    return apiRequest<{ success: boolean; updated_count: number }>(
      "/rules/reorder",
      {
        method: "POST",
        body: JSON.stringify({ rule_priorities: rulePriorities }),
      }
    );
  },
};

// =============================================================================
// Config Schema Helpers
// =============================================================================

export const COLUMN_RULE_TYPES = [
  { value: "rename", label: "Rename Column" },
  { value: "hide", label: "Hide Columns" },
  { value: "create", label: "Create Column" },
  { value: "delete", label: "Delete Columns" },
  { value: "reorder", label: "Reorder Columns" },
  { value: "copy", label: "Copy Column" },
];

export const CONDITIONAL_RULE_TYPES = [
  { value: "include_column", label: "Include Column If" },
  { value: "exclude_column", label: "Exclude Column If" },
  { value: "set_value", label: "Set Value If" },
  { value: "apply_format", label: "Apply Format If" },
];

export const SORTING_RULE_TYPES = [
  { value: "single", label: "Single Column Sort" },
  { value: "multi", label: "Multi-Column Sort" },
  { value: "custom", label: "Custom Sort" },
];

export const FILTER_RULE_TYPES = [
  { value: "include", label: "Include Rows" },
  { value: "exclude", label: "Exclude Rows" },
  { value: "distinct", label: "Distinct Rows" },
  { value: "not_null", label: "Not Null Filter" },
];

export const TOP_RULE_TYPES = [
  { value: "top_n", label: "Top N" },
  { value: "bottom_n", label: "Bottom N" },
  { value: "percent", label: "Top Percent" },
  { value: "limit", label: "Limit/Offset" },
];

export const HIGHLIGHT_RULE_TYPES = [
  { value: "cell", label: "Highlight Cell" },
  { value: "row", label: "Highlight Row" },
  { value: "column", label: "Highlight Column" },
  { value: "gradient", label: "Gradient" },
  { value: "data_bar", label: "Data Bar" },
];

export const CALCULATION_RULE_TYPES = [
  { value: "percentage", label: "Percentage" },
  { value: "aggregate", label: "Aggregate" },
  { value: "expression", label: "Expression" },
  { value: "running", label: "Running Calculation" },
  { value: "difference", label: "Difference" },
  { value: "trend", label: "Trend" },
];

export const MERGE_RULE_TYPES = [
  { value: "join", label: "Join" },
  { value: "union", label: "Union" },
  { value: "compare", label: "Compare" },
  { value: "dedupe", label: "Deduplicate" },
  { value: "conflict", label: "Conflict Resolution" },
];

export const RULE_TYPES_BY_CATEGORY: Record<
  RuleCategory,
  { value: string; label: string }[]
> = {
  column: COLUMN_RULE_TYPES,
  conditional: CONDITIONAL_RULE_TYPES,
  sorting: SORTING_RULE_TYPES,
  filter: FILTER_RULE_TYPES,
  top: TOP_RULE_TYPES,
  highlight: HIGHLIGHT_RULE_TYPES,
  calculation: CALCULATION_RULE_TYPES,
  merge: MERGE_RULE_TYPES,
};

export const CONDITION_OPERATORS = [
  { value: "equals", label: "Equals" },
  { value: "not_equals", label: "Not Equals" },
  { value: "contains", label: "Contains" },
  { value: "not_contains", label: "Does Not Contain" },
  { value: "starts_with", label: "Starts With" },
  { value: "ends_with", label: "Ends With" },
  { value: "gt", label: "Greater Than" },
  { value: "lt", label: "Less Than" },
  { value: "gte", label: "Greater Than or Equal" },
  { value: "lte", label: "Less Than or Equal" },
  { value: "in", label: "In List" },
  { value: "not_in", label: "Not In List" },
  { value: "is_null", label: "Is Null" },
  { value: "is_not_null", label: "Is Not Null" },
  { value: "between", label: "Between" },
  { value: "regex", label: "Matches Regex" },
];

export const AGGREGATE_FUNCTIONS = [
  { value: "sum", label: "Sum" },
  { value: "avg", label: "Average" },
  { value: "count", label: "Count" },
  { value: "min", label: "Minimum" },
  { value: "max", label: "Maximum" },
  { value: "median", label: "Median" },
  { value: "stddev", label: "Standard Deviation" },
  { value: "variance", label: "Variance" },
];
