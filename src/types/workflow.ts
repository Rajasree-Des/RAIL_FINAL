export type SettingType =
  | "dropdown"
  | "date"
  | "dateRange"
  | "checkbox"
  | "toggle"
  | "radio"
  | "text"
  | "number"
  | "multiSelect"
  | "searchDropdown"
  | "textarea";

export type SettingOption = {
  label: string;
  value: string;
};

export type ModuleSetting = {
  id: string;
  label: string;
  type: SettingType;
  required?: boolean;
  placeholder?: string;
  defaultValue?: string | number | boolean | string[];
  options?: SettingOption[];
  helpText?: string;
};

export type SpreadsheetColumn = {
  key: string;
  label: string;
  type: "text" | "number" | "date" | "status";
  required?: boolean;
};

export type UploadedFileRecord = {
  id: string;
  name: string;
  size: string;
  uploadedAt: string;
};

export type WorkflowVariant = "merge" | "report" | "summary";

export type WorkflowIcon =
  | "Layers"
  | "Building2"
  | "TrainFront"
  | "Tags"
  | "Route"
  | "MapPin"
  | "FileCheck";

export type ReportSourceId =
  | "division"
  | "train"
  | "types"
  | "scr-train"
  | "scr-station";

export type WorkflowDefinition = {
  id: string;
  name: string;
  order: number;
  description: string;
  variant: WorkflowVariant;
  icon: WorkflowIcon;
  settings?: ModuleSetting[];
  acceptedFiles?: string[];
  previewColumns?: SpreadsheetColumn[];
  uploadLabel?: string;
  reportSourceId?: ReportSourceId;
};

export type RowData = Record<string, string | number>;

export type GeneratedSummary = {
  id: string;
  executive: string;
  whatsapp: string;
  email: string;
  dailyHighlights: string;
  keyObservations: string;
  statistics?: Record<string, unknown>;
  generatedAt?: string;
};

/** @deprecated Use GeneratedSummary with section keys */
export type LegacyGeneratedSummary = {
  aiSummary: string;
  whatsappMessage: string;
  emailBody: string;
  pdfPreview: string;
};
