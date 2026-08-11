import { z } from "zod";

export const SettingOptionSchema = z.object({
  label: z.string(),
  value: z.string(),
});

export const WorkflowSettingSchema = z.object({
  id: z.string(),
  label: z.string(),
  type: z.string(),
  required: z.boolean().optional(),
  placeholder: z.string().nullable().optional(),
  default_value: z.unknown().optional(),
  options: z.array(SettingOptionSchema).optional(),
  help_text: z.string().nullable().optional(),
});

export const ColumnMappingSchema = z.object({
  key: z.string(),
  label: z.string(),
  type: z.string(),
  required: z.boolean().optional(),
  source_column: z.string().nullable().optional(),
});

export const WorkflowResponseSchema = z.object({
  id: z.string(),
  name: z.string(),
  order: z.number(),
  description: z.string(),
  variant: z.enum(["merge", "report", "summary"]),
  icon: z.enum(["Layers", "Building2", "TrainFront", "Tags", "Route", "MapPin", "FileCheck"]),
  upload_label: z.string().nullable().optional(),
  report_source_id: z.string().nullable().optional(),
  accepted_files: z.array(z.string()).optional(),
  settings: z.array(WorkflowSettingSchema).optional(),
  preview_columns: z.array(ColumnMappingSchema).optional(),
});

export const WorkflowListResponseSchema = z.object({
  workflows: z.array(WorkflowResponseSchema),
});

export type ApiWorkflowResponse = z.infer<typeof WorkflowResponseSchema>;
export type ApiWorkflowListResponse = z.infer<typeof WorkflowListResponseSchema>;
