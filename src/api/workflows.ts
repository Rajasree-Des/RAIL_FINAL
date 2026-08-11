import { apiRequest, ApiError } from "@/api/client";
import type { ModuleSetting, ReportSourceId, SpreadsheetColumn, WorkflowDefinition, WorkflowIcon, WorkflowVariant } from "@/types/workflow";

type ApiSettingOption = { label: string; value: string };

type ApiWorkflowSetting = {
  id: string;
  label: string;
  type: string;
  required?: boolean;
  placeholder?: string | null;
  default_value?: unknown;
  options?: ApiSettingOption[];
  help_text?: string | null;
};

type ApiColumnMapping = {
  key: string;
  label: string;
  type: string;
  required?: boolean;
  source_column?: string | null;
};

type ApiWorkflow = {
  id: string;
  name: string;
  order: number;
  description: string;
  variant: WorkflowVariant;
  icon: WorkflowIcon;
  upload_label?: string | null;
  report_source_id?: string | null;
  accepted_files?: string[];
  settings?: ApiWorkflowSetting[];
  preview_columns?: ApiColumnMapping[];
};

type WorkflowListResponse = {
  workflows: ApiWorkflow[];
};

function mapSetting(setting: ApiWorkflowSetting): ModuleSetting {
  return {
    id: setting.id,
    label: setting.label,
    type: setting.type as ModuleSetting["type"],
    required: setting.required,
    placeholder: setting.placeholder ?? undefined,
    defaultValue: setting.default_value as ModuleSetting["defaultValue"],
    options: setting.options,
    helpText: setting.help_text ?? undefined,
  };
}

function mapColumn(column: ApiColumnMapping): SpreadsheetColumn {
  return {
    key: column.key,
    label: column.label,
    type: column.type as SpreadsheetColumn["type"],
    required: column.required,
  };
}

function mapWorkflow(api: ApiWorkflow): WorkflowDefinition {
  return {
    id: api.id,
    name: api.name,
    order: api.order,
    description: api.description,
    variant: api.variant,
    icon: api.icon,
    uploadLabel: api.upload_label ?? undefined,
    reportSourceId: (api.report_source_id ?? undefined) as ReportSourceId | undefined,
    acceptedFiles: api.accepted_files ?? [],
    settings: (api.settings ?? []).map(mapSetting),
    previewColumns: (api.preview_columns ?? []).map(mapColumn),
  };
}

export async function fetchWorkflows(): Promise<WorkflowDefinition[]> {
  const response = await apiRequest<WorkflowListResponse>("/workflows");
  return response.workflows.map(mapWorkflow);
}

export async function fetchWorkflowById(workflowId: string): Promise<WorkflowDefinition | null> {
  try {
    const response = await apiRequest<ApiWorkflow>(`/workflows/${workflowId}`);
    return mapWorkflow(response);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

/** Consistent API object pattern (legacy functions remain exported). */
export const workflowsApi = {
  list: fetchWorkflows,
  get: fetchWorkflowById,
};
