import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Save, ArrowLeft, Play, AlertCircle, CheckCircle2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { Alert } from "@/components/ui/Alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";
import { templatesApi, type CreateTemplateRequest } from "@/api/templates";
import { GeneralSection } from "./components/GeneralSection";
import { InputConfigSection } from "./components/InputConfigSection";
import { ColumnMappingSection } from "./components/ColumnMappingSection";
import { SortingRulesSection } from "./components/SortingRulesSection";
import { FilteringRulesSection } from "./components/FilteringRulesSection";
import { RowRulesSection } from "./components/RowRulesSection";
import { HighlightRulesSection } from "./components/HighlightRulesSection";
import { OutputConfigSection } from "./components/OutputConfigSection";
import { useDatasetMetadata } from "@/features/report-config";

type FormData = CreateTemplateRequest;

const defaultFormData: FormData = {
  name: "",
  slug: "",
  description: "",
  source_report_id: "",
  is_enabled: true,
  metadata: {},
  input_config: {
    accepted_file_types: [".xlsx", ".xls", ".csv"],
    required_sheets: null,
    header_row: 1,
    validation_rules: {},
  },
  column_mappings: [],
  sorting_rules: [],
  filtering_rules: [],
  row_rule: {
    rule_type: "none",
    limit_value: null,
    limit_column: null,
    custom_expression: null,
  },
  highlight_rules: [],
  output_config: {
    excel_enabled: true,
    excel_config: {},
    pdf_enabled: false,
    pdf_config: {},
    ai_summary_enabled: false,
    ai_config: {},
    whatsapp_enabled: false,
    whatsapp_config: {},
    email_enabled: false,
    email_config: {},
  },
};

export function TemplateEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const isNew = id === "new";

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState<FormData>(defaultFormData);
  const [validationResult, setValidationResult] = useState<{
    is_valid: boolean;
    errors: string[];
    warnings: string[];
  } | null>(null);
  const [activeTab, setActiveTab] = useState("general");
  const reportId = formData.source_report_id || "";
  const {
    metadata: datasetMetadata,
    loading: datasetLoading,
    error: datasetError,
  } = useDatasetMetadata(reportId, { enabled: Boolean(reportId) });

  const loadTemplate = useCallback(async () => {
    if (isNew || !id) return;

    setLoading(true);
    try {
      const template = await templatesApi.get(id);
      setFormData({
        name: template.name,
        slug: template.slug,
        description: template.description || "",
        source_report_id: template.source_report_id || "",
        is_enabled: template.is_enabled,
        metadata: template.metadata,
        input_config: template.input_config || defaultFormData.input_config,
        column_mappings: template.column_mappings.map((m) => ({
          source_column: m.source_column,
          internal_field: m.internal_field,
          output_column: m.output_column,
          data_type: m.data_type,
          is_required: m.is_required,
          default_value: m.default_value,
          transform: m.transform,
          sort_order: m.sort_order,
        })),
        sorting_rules: template.sorting_rules.map((r) => ({
          column_name: r.column_name,
          direction: r.direction,
          priority: r.priority,
        })),
        filtering_rules: template.filtering_rules.map((r) => ({
          column_name: r.column_name,
          operator: r.operator as "equals" | "not_equals" | "contains" | "gt" | "lt" | "gte" | "lte" | "in" | "not_in" | "is_null" | "is_not_null",
          value: r.value,
          value_type: r.value_type,
          logic_group: r.logic_group,
        })),
        row_rule: template.row_rule
          ? {
              rule_type: template.row_rule.rule_type,
              limit_value: template.row_rule.limit_value,
              limit_column: template.row_rule.limit_column,
              custom_expression: template.row_rule.custom_expression,
            }
          : defaultFormData.row_rule,
        highlight_rules: template.highlight_rules.map((r) => ({
          column_name: r.column_name,
          condition_type: r.condition_type,
          condition_value: r.condition_value,
          highlight_color: r.highlight_color,
          text_color: r.text_color,
          is_bold: r.is_bold,
          priority: r.priority,
        })),
        output_config: template.output_config || defaultFormData.output_config,
      });
    } catch {
      showToast("error", "Failed to load template");
      navigate("/admin/templates");
    } finally {
      setLoading(false);
    }
  }, [id, isNew, navigate, showToast]);

  useEffect(() => {
    loadTemplate();
  }, [loadTemplate]);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (isNew) {
        const template = await templatesApi.create(formData);
        showToast("success", "Template created successfully");
        navigate(`/admin/templates/${template.id}/edit`);
      } else {
        await templatesApi.update(id!, formData);
        showToast("success", "Template saved successfully");
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Failed to save template";
      showToast("error", message);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (isNew || !id) {
      showToast("warning", "Save the template first to test it");
      return;
    }

    try {
      const result = await templatesApi.test(id);
      setValidationResult(result);
      if (result.is_valid) {
        showToast("success", "Template configuration is valid");
      } else {
        showToast("warning", `Found ${result.errors.length} errors`);
      }
    } catch {
      showToast("error", "Failed to validate template");
    }
  };

  const updateFormData = <K extends keyof FormData>(key: K, value: FormData[K]) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <PageHeader
          title={isNew ? "Create Template" : "Edit Template"}
          description={isNew ? "Configure a new report template" : `Editing: ${formData.name}`}
          breadcrumbs={[
            { label: "Admin" },
            { label: "Templates", href: "/admin/templates" },
            { label: isNew ? "New" : formData.name },
          ]}
        />
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => navigate("/admin/templates")}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
          {!isNew && (
            <Button variant="secondary" onClick={handleTest}>
              <Play className="mr-2 h-4 w-4" />
              Test
            </Button>
          )}
          <Button variant="primary" onClick={handleSave} disabled={saving}>
            <Save className="mr-2 h-4 w-4" />
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      {validationResult && (
        <div className="mb-6 space-y-2">
          {validationResult.errors.map((error, i) => (
            <Alert key={`error-${i}`} variant="error">
              <AlertCircle className="h-4 w-4" />
              {error}
            </Alert>
          ))}
          {validationResult.warnings.map((warning, i) => (
            <Alert key={`warning-${i}`} variant="warning">
              <AlertCircle className="h-4 w-4" />
              {warning}
            </Alert>
          ))}
          {validationResult.is_valid && validationResult.errors.length === 0 && (
            <Alert variant="success">
              <CheckCircle2 className="h-4 w-4" />
              Template configuration is valid
            </Alert>
          )}
        </div>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-6">
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="input">Input Config</TabsTrigger>
          <TabsTrigger value="columns">Column Mappings</TabsTrigger>
          <TabsTrigger value="sorting">Sorting</TabsTrigger>
          <TabsTrigger value="filtering">Filtering</TabsTrigger>
          <TabsTrigger value="rows">Row Rules</TabsTrigger>
          <TabsTrigger value="highlight">Highlighting</TabsTrigger>
          <TabsTrigger value="output">Output</TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <GeneralSection
            data={{
              name: formData.name,
              slug: formData.slug || "",
              description: formData.description || "",
              source_report_id: formData.source_report_id || "",
              is_enabled: formData.is_enabled ?? true,
            }}
            onChange={(data) => {
              updateFormData("name", data.name);
              updateFormData("slug", data.slug);
              updateFormData("description", data.description);
              updateFormData("source_report_id", data.source_report_id);
              updateFormData("is_enabled", data.is_enabled);
            }}
          />
        </TabsContent>

        <TabsContent value="input">
          <InputConfigSection
            data={formData.input_config || defaultFormData.input_config!}
            onChange={(data) => updateFormData("input_config", data)}
          />
        </TabsContent>

        <TabsContent value="columns">
          <ColumnMappingSection
            data={formData.column_mappings || []}
            onChange={(data) => updateFormData("column_mappings", data)}
          />
        </TabsContent>

        <TabsContent value="sorting">
          <SortingRulesSection
            data={formData.sorting_rules || []}
            columns={formData.column_mappings?.map((m) => m.internal_field) || []}
            onChange={(data) => updateFormData("sorting_rules", data)}
          />
        </TabsContent>

        <TabsContent value="filtering">
          <FilteringRulesSection
            data={formData.filtering_rules || []}
            columns={datasetMetadata?.columns ?? []}
            loading={datasetLoading}
            error={
              !reportId
                ? "Select a source report in the General tab to load original dataset columns."
                : datasetError
            }
            onChange={(data) => updateFormData("filtering_rules", data)}
          />
        </TabsContent>

        <TabsContent value="rows">
          <RowRulesSection
            data={formData.row_rule || defaultFormData.row_rule!}
            columns={formData.column_mappings?.map((m) => m.internal_field) || []}
            onChange={(data) => updateFormData("row_rule", data)}
          />
        </TabsContent>

        <TabsContent value="highlight">
          <HighlightRulesSection
            data={formData.highlight_rules || []}
            columns={formData.column_mappings?.map((m) => m.internal_field) || []}
            onChange={(data) => updateFormData("highlight_rules", data)}
          />
        </TabsContent>

        <TabsContent value="output">
          <OutputConfigSection
            data={formData.output_config || defaultFormData.output_config!}
            onChange={(data) => updateFormData("output_config", data)}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
