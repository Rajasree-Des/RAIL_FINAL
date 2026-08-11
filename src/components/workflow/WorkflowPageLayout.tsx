import { useState, useCallback, useEffect, useMemo, useRef, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { SettingsCard } from "./SettingsCard";
import { PreviewTable } from "./PreviewTable";
import { SectionedPreviewTable } from "./SectionedPreviewTable";
import { OutputCard } from "./OutputCard";
import { ActionBar } from "./ActionBar";
import { useManualReportGeneration } from "./useManualReportGeneration";
import { cn } from "@/utils/cn";
import { formatFileSize, reportsApi, resolveReportSlug } from "@/api/reports";
import {
  getReportDisplayName,
  getReportDownloadName,
} from "@/utils/reportDisplayNames";
import {
  defaultReportDateFrom,
  defaultReportDateTo,
  formatReportDateLabel,
  validateReportDateRange,
} from "@/utils/reportDateRange";
import {
  FilterBuilder,
  VisibleColumnsSection,
  GroupedOutputColumnsSection,
  EditDefaultFiltersDialog,
  useDatasetMetadata,
  useOutputColumnCatalog,
  usesManualColumnSelection,
  usesOutputColumnCatalog,
  useReactiveOutputPreview,
  usesReactiveOutputPreview,
  type FilterCondition,
  type ReportId,
  type ColumnMetadata,
} from "@/features/report-config";
import { Button } from "@/components/ui/Button";

interface SettingField {
  id: string;
  label: string;
  type: "text" | "number" | "select" | "date";
  value: string | number;
  options?: { value: string; label: string }[];
  placeholder?: string;
}

interface Column {
  key: string;
  header: string;
  width?: string;
}

interface WorkflowPageLayoutProps {
  reportId: ReportId;
  title: string;
  description: string;
  breadcrumbs?: { label: string; href?: string }[];
  settingsFields: SettingField[];
  advancedFields?: SettingField[];
  previewColumns?: Column[];
  /** Optional content rendered above Report Settings (page-specific only). */
  beforeSettings?: ReactNode;
  /** When false, hides the Advanced Settings accordion (column picker / filters UI). */
  showAdvancedSettings?: boolean;
}

function applyDefaultDateRange(fields: SettingField[]): SettingField[] {
  return fields.map((field) => {
    if (field.id === "dateFrom") {
      return { ...field, value: defaultReportDateFrom() };
    }
    if (field.id === "dateTo") {
      return { ...field, value: defaultReportDateTo() };
    }
    return field;
  });
}

export function WorkflowPageLayout({
  reportId,
  title: _title,
  description,
  breadcrumbs,
  settingsFields: initialSettings,
  advancedFields: initialAdvanced = [],
  previewColumns: defaultPreviewColumns = [],
  beforeSettings,
  showAdvancedSettings = true,
}: WorkflowPageLayoutProps) {
  const outputCatalogMode = usesOutputColumnCatalog(reportId);
  const reactivePreviewMode = usesReactiveOutputPreview(reportId);
  const columnSelectionEnabled = usesManualColumnSelection(reportId);
  const displayTitle = getReportDisplayName(resolveReportSlug(reportId));
  const downloadTitle = getReportDownloadName(resolveReportSlug(reportId));
  const resolvedBreadcrumbs = breadcrumbs ?? [
    { label: "Report Configuration" },
    { label: displayTitle },
  ];
  const { metadata, loading: metadataLoading, error: metadataError } = useDatasetMetadata(reportId, {
    enabled: columnSelectionEnabled && !outputCatalogMode,
  });
  const {
    columns: outputColumns,
    defaultColumnIds: catalogDefaultColumnIds,
    loading: outputLoading,
    error: outputError,
  } = useOutputColumnCatalog(reportId);
  const columnPickerColumns = outputCatalogMode ? outputColumns : metadata?.columns ?? [];
  const columnPickerLoading = outputCatalogMode ? outputLoading : metadataLoading;
  const columnPickerError = outputCatalogMode ? outputError : metadataError;
  const [settings, setSettings] = useState(() => applyDefaultDateRange(initialSettings));
  const [advancedSettings, setAdvancedSettings] = useState(initialAdvanced);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [filterConditions, setFilterConditions] = useState<FilterCondition[]>([]);
  const [visibleColumnIds, setVisibleColumnIds] = useState<string[]>([]);
  const [savedDefaultColumnIds, setSavedDefaultColumnIds] = useState<string[]>([]);
  const [editDefaultsOpen, setEditDefaultsOpen] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const userTouchedColumnsRef = useRef(false);

  const effectiveDefaultColumnIds =
    savedDefaultColumnIds.length > 0 ? savedDefaultColumnIds : catalogDefaultColumnIds;

  const columnLabelMap = useMemo(
    () =>
      Object.fromEntries(
        columnPickerColumns.map((column: ColumnMetadata) => [
          column.id,
          column.displayName,
        ]),
      ),
    [columnPickerColumns],
  );

  const handleVisibleColumnIdsChange = useCallback((next: string[]) => {
    userTouchedColumnsRef.current = true;
    if (reportId === "merging") {
      console.info("report1_selected_columns_changed", {
        selected_column_ids: next,
        count: next.length,
      });
    } else if (reportId === "division") {
      console.info("report2_selected_columns_changed", {
        selected_column_ids: next,
        count: next.length,
      });
    }
    setVisibleColumnIds(next);
  }, [reportId]);

  const {
    status,
    manualStatus,
    runState,
    previewData,
    previewColumns: dynamicPreviewColumns,
    errorMessage,
    handleGenerate,
    handleSaveConfiguration,
    handleDownload,
    handleDownloadExcel,
    handleDownloadPdf,
    handlePreviewPdf,
    resetGeneration,
    canDownload,
    canDownloadExcel,
    canDownloadPdf,
    canPreviewPdf,
    dualOutputMode,
  } = useManualReportGeneration({
    reportId,
    visibleColumnIds,
    columnLabels: columnLabelMap,
    filterConditions,
    settings,
    defaultSelectedColumnIds: savedDefaultColumnIds,
  });

  const reactivePreview = useReactiveOutputPreview({
    reportId,
    selectedColumnIds: visibleColumnIds,
    enabled: reactivePreviewMode && status !== "processing",
  });

  useEffect(() => {
    if (!columnSelectionEnabled) {
      setVisibleColumnIds([]);
      return;
    }
    if (outputCatalogMode) {
      if (!outputColumns.length) return;
      setVisibleColumnIds((current) =>
        current.length > 0
          ? current
          : effectiveDefaultColumnIds.length > 0
            ? effectiveDefaultColumnIds
            : outputColumns.map((column: ColumnMetadata) => column.id),
      );
      return;
    }
    if (!metadata?.columns.length) return;
    setVisibleColumnIds((current) =>
      current.length > 0 ? current : metadata.columns.map((column: ColumnMetadata) => column.id),
    );
  }, [metadata, outputCatalogMode, outputColumns, effectiveDefaultColumnIds, columnSelectionEnabled]);

  useEffect(() => {
    let cancelled = false;
    void reportsApi.loadConfig(reportId).then((saved) => {
      if (cancelled || !saved) return;
      if (columnSelectionEnabled && saved.default_selected_column_ids?.length) {
        setSavedDefaultColumnIds(saved.default_selected_column_ids);
      }
      // Prefer explicitly saved default filters for new runs; else last selection.
      const initialColumns = columnSelectionEnabled
        ? saved.default_selected_column_ids?.length
          ? saved.default_selected_column_ids
          : saved.selected_column_ids?.length
            ? saved.selected_column_ids
            : []
        : [];
      if (initialColumns.length && !userTouchedColumnsRef.current) {
        setVisibleColumnIds(initialColumns);
      }
      if (saved.export_format) {
        setSettings((prev) =>
          prev.map((field) =>
            field.id === "exportFormat" ? { ...field, value: saved.export_format } : field,
          ),
        );
      }
      if (saved.filter_conditions?.length) {
        setFilterConditions(saved.filter_conditions as unknown as FilterCondition[]);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [reportId, columnSelectionEnabled]);

  const handleSettingChange = useCallback((id: string, value: string | number) => {
    setSettings((prev) =>
      prev.map((field) => (field.id === id ? { ...field, value } : field)),
    );
  }, []);

  const handleAdvancedChange = useCallback((id: string, value: string | number) => {
    setAdvancedSettings((prev) =>
      prev.map((field) => (field.id === id ? { ...field, value } : field)),
    );
  }, []);

  const handleSave = useCallback(async () => {
    try {
      await handleSaveConfiguration();
      setSaveMessage("Configuration saved.");
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save configuration.");
    }
  }, [handleSaveConfiguration]);

  const handleReset = useCallback(() => {
    resetGeneration();
    setSettings(applyDefaultDateRange(initialSettings));
    setAdvancedSettings(initialAdvanced);
    setFilterConditions([]);
    userTouchedColumnsRef.current = false;
    if (!columnSelectionEnabled) {
      setVisibleColumnIds([]);
    } else if (outputCatalogMode) {
      setVisibleColumnIds(
        effectiveDefaultColumnIds.length > 0
          ? effectiveDefaultColumnIds
          : outputColumns.map((column: ColumnMetadata) => column.id),
      );
    } else {
      setVisibleColumnIds(metadata?.columns.map((column: ColumnMetadata) => column.id) ?? []);
    }
  }, [
    initialAdvanced,
    initialSettings,
    metadata,
    outputCatalogMode,
    outputColumns,
    effectiveDefaultColumnIds,
    resetGeneration,
    columnSelectionEnabled,
  ]);

  const handleSaveDefaultFilters = useCallback(
    async (columnIds: string[]) => {
      const exportFormat = settings.find((field) => field.id === "exportFormat")?.value;
      const format =
        exportFormat === "pdf" || exportFormat === "csv" || exportFormat === "xlsx"
          ? exportFormat
          : "xlsx";
      await reportsApi.saveConfig(reportId, {
        selected_column_ids: visibleColumnIds.length > 0 ? visibleColumnIds : columnIds,
        column_order: visibleColumnIds.length > 0 ? visibleColumnIds : columnIds,
        default_selected_column_ids: columnIds,
        export_format: format,
        config_overrides: Object.fromEntries(
          settings
            .filter(
              (field) =>
                field.id !== "exportFormat" &&
                field.id !== "reportDate" &&
                field.id !== "dateFrom" &&
                field.id !== "dateTo",
            )
            .map((field) => [field.id, field.value]),
        ),
        filter_conditions: filterConditions.map(
          ({ id, columnId, operator, value, valueTo, logic }) => ({
            id,
            columnId,
            operator,
            value,
            valueTo,
            logic,
          }),
        ),
      });
      setSavedDefaultColumnIds(columnIds);
      // Apply defaults to the current run selection when the user hasn't customized columns.
      if (!userTouchedColumnsRef.current) {
        setVisibleColumnIds(columnIds);
      }
      setSaveMessage("Default column filters saved.");
      setTimeout(() => setSaveMessage(null), 3000);
    },
    [reportId, visibleColumnIds, settings, filterConditions],
  );

  const triggerBlobDownload = useCallback((blob: Blob, filename: string) => {
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  }, []);

  const onDownload = useCallback(async () => {
    try {
      const { blob, filename } = await handleDownload();
      triggerBlobDownload(blob, filename);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Download failed.");
    }
  }, [handleDownload, triggerBlobDownload]);

  const onDownloadExcel = useCallback(async () => {
    try {
      const { blob, filename } = await handleDownloadExcel();
      triggerBlobDownload(blob, filename);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Excel download failed.");
    }
  }, [handleDownloadExcel, triggerBlobDownload]);

  const onDownloadPdf = useCallback(async () => {
    try {
      const { blob, filename } = await handleDownloadPdf();
      triggerBlobDownload(blob, filename);
    } catch (err) {
      alert(err instanceof Error ? err.message : "PDF download failed.");
    }
  }, [handleDownloadPdf, triggerBlobDownload]);

  const onPreviewPdf = useCallback(() => {
    try {
      handlePreviewPdf();
    } catch (err) {
      alert(err instanceof Error ? err.message : "PDF preview failed.");
    }
  }, [handlePreviewPdf]);

  const datasetSourceLabel = metadata?.sourceFilename ?? "Original RailMadad dataset";
  const runPreviewColumns =
    dynamicPreviewColumns.length > 0 ? dynamicPreviewColumns : defaultPreviewColumns;
  const activePreviewColumns = reactivePreviewMode
    ? reactivePreview.previewColumns.length > 0
      ? reactivePreview.previewColumns
      : runPreviewColumns
    : runPreviewColumns;
  const activePreviewData = reactivePreviewMode
    ? reactivePreview.previewData.length > 0
      ? reactivePreview.previewData
      : previewData
    : previewData;
  const previewEmptyMessage = reactivePreviewMode
    ? reactivePreview.emptyMessage ||
      "No generated report data is available for preview."
    : "No preview available. Generate the report to preview processed output.";
  const dateFromValue = String(settings.find((field) => field.id === "dateFrom")?.value ?? "");
  const dateToValue = String(settings.find((field) => field.id === "dateTo")?.value ?? "");
  const reportDateLabel =
    runState?.report_date ??
    (dateFromValue && dateToValue
      ? formatReportDateLabel(dateFromValue, dateToValue)
      : formatReportDateLabel(defaultReportDateFrom(), defaultReportDateTo()));

  const onGenerate = useCallback(() => {
    const validationError = validateReportDateRange(dateFromValue, dateToValue);
    if (validationError) {
      alert(validationError);
      return;
    }
    void handleGenerate();
  }, [dateFromValue, dateToValue, handleGenerate]);

  return (
    <div className="space-y-8">
      <PageHeader title={displayTitle} description={description} breadcrumbs={resolvedBreadcrumbs} />

      {beforeSettings}

      <SettingsCard
        title="Report Settings"
        description="Configure how this report should be generated"
        fields={settings}
        onChange={handleSettingChange}
        disabled={status === "processing"}
      />

      {showAdvancedSettings ? (
        <div className="overflow-hidden rounded-2xl border border-rail-line bg-white shadow-card transition-all duration-200 hover:shadow-premium">
          <button
            type="button"
            onClick={() => setAdvancedOpen((open) => !open)}
            className="flex w-full items-center justify-between px-6 py-5 text-left transition-colors hover:bg-surface/50"
          >
            <div>
              <span className="text-sm font-semibold text-slate-900">Advanced Settings</span>
              <p className="mt-0.5 text-xs text-slate-500">
                Dynamic filters, visible columns, highlights and export options
              </p>
            </div>
            <ChevronDown
              className={cn(
                "h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200",
                advancedOpen && "rotate-180",
              )}
            />
          </button>

          {advancedOpen && (
            <div className="space-y-6 border-t border-rail-line px-6 py-6">
              <div className="rounded-xl border border-rail-line bg-white p-4">
                <p className="text-xs text-slate-500">
                  {outputCatalogMode ? (
                    <>
                      Output columns:{" "}
                      <span className="font-medium text-slate-700">
                        {columnPickerColumns.length} selectable fields
                      </span>
                    </>
                  ) : (
                    <>
                      Source dataset:{" "}
                      <span className="font-medium text-slate-700">{datasetSourceLabel}</span>
                      {metadata ? ` · ${metadata.columns.length} original columns` : ""}
                    </>
                  )}
                </p>
              </div>

              {!outputCatalogMode && (
                <FilterBuilder
                  columns={metadata?.columns ?? []}
                  conditions={filterConditions}
                  onChange={setFilterConditions}
                  loading={metadataLoading}
                  error={metadataError}
                  disabled={status === "processing"}
                />
              )}

              <div className={outputCatalogMode ? "" : "border-t border-rail-line pt-6"}>
                {outputCatalogMode ? (
                  <>
                    <div className="mb-3 flex flex-wrap justify-end">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => setEditDefaultsOpen(true)}
                        disabled={status === "processing" || columnPickerLoading}
                      >
                        Edit Default Filters
                      </Button>
                    </div>
                    <GroupedOutputColumnsSection
                      columns={columnPickerColumns}
                      selectedColumnIds={visibleColumnIds}
                      defaultColumnIds={effectiveDefaultColumnIds}
                      onChange={handleVisibleColumnIdsChange}
                      disabled={status === "processing" || columnPickerLoading}
                    />
                    <EditDefaultFiltersDialog
                      open={editDefaultsOpen}
                      onOpenChange={setEditDefaultsOpen}
                      columns={columnPickerColumns}
                      catalogDefaultColumnIds={catalogDefaultColumnIds}
                      savedDefaultColumnIds={effectiveDefaultColumnIds}
                      onSave={handleSaveDefaultFilters}
                      disabled={status === "processing" || columnPickerLoading}
                    />
                  </>
                ) : (
                  <VisibleColumnsSection
                    columns={columnPickerColumns}
                    selectedColumnIds={visibleColumnIds}
                    onChange={handleVisibleColumnIdsChange}
                    disabled={status === "processing" || columnPickerLoading}
                  />
                )}
                {columnPickerError ? (
                  <p className="mt-2 text-xs text-danger">{columnPickerError}</p>
                ) : null}
              </div>

              {advancedSettings.length > 0 && (
                <div className="border-t border-rail-line pt-2">
                  <SettingsCard
                    title=""
                    description="Highlight rules and export options"
                    fields={advancedSettings}
                    onChange={handleAdvancedChange}
                    disabled={status === "processing"}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      ) : null}

      {saveMessage && (
        <p className="rounded-lg border border-green-200 bg-green-50 px-4 py-2 text-sm text-green-800">
          {saveMessage}
        </p>
      )}

      <ActionBar
        onGenerate={onGenerate}
        onReset={handleReset}
        onDownload={() => void onDownload()}
        onSave={() => void handleSave()}
        generateDisabled={
          status === "processing" ||
          (showAdvancedSettings && visibleColumnIds.length === 0)
        }
        resetDisabled={status === "idle" && previewData.length === 0}
        downloadDisabled={!canDownload}
        showDownload={!dualOutputMode}
        isProcessing={status === "processing"}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        {reactivePreviewMode && reportId === "types" && reactivePreview.previewSections.length > 0 ? (
          <SectionedPreviewTable
            title="Report Preview"
            description={`Preview of generated report (report date ${reportDateLabel})`}
            sections={reactivePreview.previewSections}
            emptyMessage={previewEmptyMessage}
          />
        ) : (
          <PreviewTable
            title="Report Preview"
            description={`Preview of generated report (report date ${reportDateLabel})`}
            columns={activePreviewColumns}
            data={activePreviewData}
            emptyMessage={previewEmptyMessage}
          />
        )}

        <OutputCard
          title="Generated Output"
          description="Download your report after generation"
          status={status}
          manualStatus={manualStatus}
          outputFile={
            status === "completed" && runState
              ? {
                  name:
                    dualOutputMode && runState.pdf_filename
                      ? `${runState.excel_filename ?? "report.xlsx"} · ${runState.pdf_filename}`
                      : runState.excel_filename ??
                        runState.output_filename ??
                        `${downloadTitle.toLowerCase().replace(/\s+/g, "_")}_report`,
                  size: formatFileSize(
                    dualOutputMode
                      ? (runState.excel_file_size ?? runState.output_file_size)
                      : runState.output_file_size,
                  ),
                  generatedAt: runState.generated_at
                    ? new Date(runState.generated_at).toLocaleString()
                    : new Date().toLocaleString(),
                  rowCount: runState.processed_row_count ?? runState.source_row_count ?? undefined,
                  reportDate: runState.report_date ?? undefined,
                }
              : undefined
          }
          errorMessage={errorMessage ?? undefined}
          onDownload={() => void onDownload()}
          dualOutputMode={dualOutputMode}
          onPreviewPdf={onPreviewPdf}
          onDownloadPdf={() => void onDownloadPdf()}
          onDownloadExcel={() => void onDownloadExcel()}
          previewPdfDisabled={!canPreviewPdf}
          downloadPdfDisabled={!canDownloadPdf}
          downloadExcelDisabled={!canDownloadExcel}
          disabled={!canDownload}
        />
      </div>
    </div>
  );
}
