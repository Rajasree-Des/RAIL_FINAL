import { useCallback, useEffect, useRef, useState } from "react";
import { isAbortError, ApiError } from "@/api/client";
import {
  canDownloadManualStatus,
  canDownloadExcel,
  canDownloadPdf,
  canPreviewPdf,
  isTerminalManualStatus,
  reportsApi,
  resolveReportSlug,
  usesDualManualArtifacts,
  type ManualRunStatus,
  type ManualUiStatus,
} from "@/api/reports";
import type { FilterCondition } from "@/features/report-config";
import { usesReactiveOutputPreview } from "@/features/report-config/hooks/useReactiveOutputPreview";

const POLL_MS = 2500;

type WorkflowUiStatus = "idle" | "processing" | "completed" | "error";

function mapUiStatus(manualStatus: ManualUiStatus): WorkflowUiStatus {
  if (manualStatus === "Completed") return "completed";
  if (manualStatus === "Failed") return "error";
  if (manualStatus === "Waiting") return "idle";
  return "processing";
}

interface UseManualReportGenerationOptions {
  reportId: string;
  visibleColumnIds: string[];
  columnLabels?: Record<string, string>;
  filterConditions: FilterCondition[];
  settings: Array<{ id: string; value: string | number }>;
  /** Persisted default Output Column Filters (optional). */
  defaultSelectedColumnIds?: string[];
}

export function useManualReportGeneration({
  reportId,
  visibleColumnIds,
  columnLabels,
  filterConditions,
  settings,
  defaultSelectedColumnIds,
}: UseManualReportGenerationOptions) {
  const [status, setStatus] = useState<WorkflowUiStatus>("idle");
  const [manualStatus, setManualStatus] = useState<ManualUiStatus>("Waiting");
  const [runState, setRunState] = useState<ManualRunStatus | null>(null);
  const [previewData, setPreviewData] = useState<Record<string, string | number>[]>([]);
  const [previewColumns, setPreviewColumns] = useState<Array<{ key: string; header: string }>>(
    [],
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const runIdRef = useRef<string | null>(null);
  const generateInFlightRef = useRef(false);
  const reportSlug = resolveReportSlug(reportId);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const applyRunState = useCallback((next: ManualRunStatus) => {
    setRunState(next);
    setManualStatus(next.status);
    setStatus(mapUiStatus(next.status));
    setErrorMessage(next.status === "Failed" ? next.error ?? "Report generation failed" : null);
    if (isTerminalManualStatus(next.status)) {
      generateInFlightRef.current = false;
    }

    if (next.preview_rows.length > 0) {
      setPreviewData(next.preview_rows);
      const columns =
        next.visible_columns.length > 0
          ? next.visible_columns.map((header) => ({ key: header, header }))
          : Object.keys(next.preview_rows[0] ?? {}).map((key) => ({ key, header: key }));
      setPreviewColumns(columns);
    }
  }, []);

  const pollRun = useCallback(async () => {
    const runId = runIdRef.current;
    if (!runId) return;
    try {
      const next = await reportsApi.getRunStatus(runId, reportSlug);
      applyRunState(next);
      if (isTerminalManualStatus(next.status)) {
        stopPolling();
      }
    } catch (err) {
      if (isAbortError(err)) {
        return;
      }
      stopPolling();
      setStatus("error");
      setManualStatus("Failed");
      setErrorMessage(err instanceof Error ? err.message : "Failed to poll run status");
    }
  }, [applyRunState, reportSlug, stopPolling]);

  const startPolling = useCallback(
    (runId: string) => {
      runIdRef.current = runId;
      stopPolling();
      void pollRun();
      pollRef.current = setInterval(() => {
        void pollRun();
      }, POLL_MS);
    },
    [pollRun, stopPolling],
  );

  useEffect(() => () => stopPolling(), [stopPolling]);

  const buildExportFormat = useCallback((): "xlsx" | "pdf" | "csv" => {
    const raw = settings.find((field) => field.id === "exportFormat")?.value;
    if (raw === "pdf" || raw === "csv" || raw === "xlsx") return raw;
    return "xlsx";
  }, [settings]);

  const buildDateRange = useCallback(() => {
    const dateFrom = settings.find((field) => field.id === "dateFrom")?.value;
    const dateTo = settings.find((field) => field.id === "dateTo")?.value;
    return {
      date_from: dateFrom != null ? String(dateFrom) : undefined,
      date_to: dateTo != null ? String(dateTo) : undefined,
    };
  }, [settings]);

  const buildConfigOverrides = useCallback(() => {
    const overrides: Record<string, string | number> = {};
    for (const field of settings) {
      if (
        field.id === "exportFormat" ||
        field.id === "reportDate" ||
        field.id === "dateFrom" ||
        field.id === "dateTo"
      ) {
        continue;
      }
      overrides[field.id] = field.value;
    }
    return overrides;
  }, [settings]);

  const handleGenerate = useCallback(async () => {
    if (generateInFlightRef.current || status === "processing") {
      if (runIdRef.current) {
        startPolling(runIdRef.current);
      }
      return;
    }
    generateInFlightRef.current = true;
    setStatus("processing");
    setManualStatus("Extracting");
    setErrorMessage(null);
    if (!usesReactiveOutputPreview(reportId)) {
      setPreviewData([]);
    }
    setRunState(null);

    const columnOrder =
      visibleColumnIds.length > 0 ? visibleColumnIds : [];
    const selectedColumnLabels = columnOrder.map(
      (columnId) => columnLabels?.[columnId] ?? columnId,
    );

    console.info("[report-generate] column selection", {
      report_slug: reportSlug,
      selected_column_ids: columnOrder,
      selected_column_labels: selectedColumnLabels,
      selected_column_count: columnOrder.length,
      column_order: columnOrder,
      requested_formats: ["xlsx", "pdf"],
      configuration_source: "manual_snapshot",
    });

    try {
      const response = await reportsApi.generate(reportId, {
        report_slug: reportSlug,
        ...buildDateRange(),
        selected_column_ids: columnOrder,
        column_order: columnOrder,
        configuration_source: "manual_snapshot",
        requested_formats: ["xlsx", "pdf"],
        force_fresh_extraction: true,
        export_format: buildExportFormat(),
        config_overrides: buildConfigOverrides(),
        filter_conditions: filterConditions.map(({ id, columnId, operator, value, valueTo, logic }) => ({
          id,
          columnId,
          operator,
          value,
          valueTo,
          logic,
        })),
      });
      startPolling(response.run_id);
    } catch (err) {
      generateInFlightRef.current = false;
      setStatus("error");
      setManualStatus("Failed");
      if (err instanceof ApiError && err.code === "AUTOMATION_ALREADY_RUNNING") {
        setErrorMessage(
          "Another report is already generating. Wait for it to finish, then try again.",
        );
      } else if (err instanceof ApiError) {
        setErrorMessage(err.message || "Failed to start report generation");
      } else {
        setErrorMessage(err instanceof Error ? err.message : "Failed to start report generation");
      }
    }
  }, [
    reportId,
    reportSlug,
    visibleColumnIds,
    columnLabels,
    filterConditions,
    buildExportFormat,
    buildDateRange,
    buildConfigOverrides,
    startPolling,
    status,
  ]);

  const handleSaveConfiguration = useCallback(async () => {
    const columnOrder = visibleColumnIds.length > 0 ? visibleColumnIds : [];
    await reportsApi.saveConfig(reportId, {
      selected_column_ids: columnOrder,
      column_order: columnOrder,
      ...(defaultSelectedColumnIds?.length
        ? { default_selected_column_ids: defaultSelectedColumnIds }
        : {}),
      export_format: buildExportFormat(),
      config_overrides: buildConfigOverrides(),
      filter_conditions: filterConditions.map(({ id, columnId, operator, value, valueTo, logic }) => ({
        id,
        columnId,
        operator,
        value,
        valueTo,
        logic,
      })),
    });
  }, [
    reportId,
    visibleColumnIds,
    defaultSelectedColumnIds,
    filterConditions,
    buildExportFormat,
    buildConfigOverrides,
  ]);

  const handleDownload = useCallback(async () => {
    if (!runState || !canDownloadManualStatus(runState)) {
      throw new Error("Generate the report first.");
    }
    if (usesDualManualArtifacts(runState.report_slug) && canDownloadExcel(runState)) {
      return reportsApi.downloadManualExcel(runState);
    }
    return reportsApi.downloadCurrentRun(runState);
  }, [runState]);

  const handleDownloadExcel = useCallback(async () => {
    if (!runState || !canDownloadExcel(runState)) {
      throw new Error("Generate the report first.");
    }
    return reportsApi.downloadManualExcel(runState);
  }, [runState]);

  const handleDownloadPdf = useCallback(async () => {
    if (!runState || !canDownloadPdf(runState)) {
      throw new Error("Generate the report first.");
    }
    return reportsApi.downloadManualPdf(runState);
  }, [runState]);

  const handlePreviewPdf = useCallback(() => {
    if (!runState || !canPreviewPdf(runState)) {
      throw new Error("Generate the report first.");
    }
    window.open(reportsApi.previewManualPdf(runState), "_blank", "noopener,noreferrer");
  }, [runState]);

  const resetGeneration = useCallback(() => {
    stopPolling();
    runIdRef.current = null;
    generateInFlightRef.current = false;
    setRunState(null);
    setPreviewData([]);
    setPreviewColumns([]);
    setStatus("idle");
    setManualStatus("Waiting");
    setErrorMessage(null);
  }, [stopPolling]);

  return {
    status,
    manualStatus,
    runState,
    previewData,
    previewColumns,
    errorMessage,
    handleGenerate,
    handleSaveConfiguration,
    handleDownload,
    handleDownloadExcel,
    handleDownloadPdf,
    handlePreviewPdf,
    resetGeneration,
    canDownload: runState ? canDownloadManualStatus(runState) : false,
    canDownloadExcel: runState ? canDownloadExcel(runState) : false,
    canDownloadPdf: runState ? canDownloadPdf(runState) : false,
    canPreviewPdf: runState ? canPreviewPdf(runState) : false,
    dualOutputMode: usesDualManualArtifacts(reportSlug),
  };
}
