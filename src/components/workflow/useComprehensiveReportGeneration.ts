import { useCallback, useEffect, useRef, useState } from "react";
import { isAbortError, ApiError } from "@/api/client";
import {
  canDownloadExcel,
  canDownloadPdf,
  canDownloadManualStatus,
  canPreviewPdf,
  isTerminalManualStatus,
  reportsApi,
  type ManualRunStatus,
  type ManualUiStatus,
} from "@/api/reports";
import {
  buildConfigFingerprint,
  buildSectionsPayload,
  COMPREHENSIVE_REPORT_ID,
  type SectionColumnState,
  unionColumnIds,
  validateSectionSelections,
} from "@/features/workflows/comprehensiveConstants";

const POLL_MS = 2500;
const REPORT_SLUG = COMPREHENSIVE_REPORT_ID;

export type ComprehensiveUiPhase =
  | "idle"
  | "unsaved"
  | "saving"
  | "generating"
  | "generated"
  | "failed";

type WorkflowUiStatus = "idle" | "processing" | "completed" | "error";

function mapUiStatus(manualStatus: ManualUiStatus): WorkflowUiStatus {
  if (manualStatus === "Completed") return "completed";
  if (manualStatus === "Failed") return "error";
  if (manualStatus === "Waiting") return "idle";
  return "processing";
}

export type ComprehensiveExportFormat = "xlsx" | "pdf" | "both";

function resolveRequestedFormats(
  exportFormat: ComprehensiveExportFormat,
): Array<"xlsx" | "pdf"> {
  if (exportFormat === "pdf") return ["pdf"];
  if (exportFormat === "xlsx") return ["xlsx"];
  return ["xlsx", "pdf"];
}

export function resolveComprehensiveExportFormat(
  saved: {
    export_format?: string;
    config_overrides?: Record<string, unknown>;
  },
): ComprehensiveExportFormat {
  const requested = saved.config_overrides?.requested_formats;
  if (Array.isArray(requested)) {
    const formats = requested.map(String);
    if (formats.includes("pdf") && formats.includes("xlsx")) return "both";
    if (formats.includes("pdf")) return "pdf";
    return "xlsx";
  }
  if (saved.export_format === "pdf") return "pdf";
  // Legacy configs stored dual-output preference as xlsx; default comprehensive to both.
  return "both";
}

function resolveApiExportFormat(
  exportFormat: ComprehensiveExportFormat,
): "xlsx" | "pdf" | "csv" {
  if (exportFormat === "pdf") return "pdf";
  return "xlsx";
}

interface SettingField {
  id: string;
  value: string | number;
}

interface UseComprehensiveReportGenerationOptions {
  sectionStates: Record<string, SectionColumnState>;
  settings: SettingField[];
  defaultSections?: Record<string, { selected_column_ids: string[] }>;
}

export function useComprehensiveReportGeneration({
  sectionStates,
  settings,
  defaultSections,
}: UseComprehensiveReportGenerationOptions) {
  const [status, setStatus] = useState<WorkflowUiStatus>("idle");
  const [manualStatus, setManualStatus] = useState<ManualUiStatus>("Waiting");
  const [phase, setPhase] = useState<ComprehensiveUiPhase>("idle");
  const [runState, setRunState] = useState<ManualRunStatus | null>(null);
  const [previewData, setPreviewData] = useState<Record<string, string | number>[]>([]);
  const [previewColumns, setPreviewColumns] = useState<Array<{ key: string; header: string }>>(
    [],
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [settingsChanged, setSettingsChanged] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const runIdRef = useRef<string | null>(null);
  const generateInFlightRef = useRef(false);
  const lastSuccessfulFingerprintRef = useRef<string | null>(null);
  const generateFingerprintRef = useRef<string | null>(null);

  const dateFrom = String(settings.find((f) => f.id === "dateFrom")?.value ?? "");
  const dateTo = String(settings.find((f) => f.id === "dateTo")?.value ?? "");
  const exportFormatRaw = String(settings.find((f) => f.id === "exportFormat")?.value ?? "both");
  const exportFormat: ComprehensiveExportFormat =
    exportFormatRaw === "pdf" || exportFormatRaw === "xlsx" || exportFormatRaw === "both"
      ? exportFormatRaw
      : "both";

  const currentFingerprint = buildConfigFingerprint(
    dateFrom,
    dateTo,
    exportFormat,
    sectionStates,
  );

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

    if (next.status === "Failed") {
      setPhase("failed");
      setErrorMessage(next.error ?? "Report generation failed");
      generateInFlightRef.current = false;
    } else if (next.status === "Completed") {
      setPhase("generated");
      setErrorMessage(null);
      lastSuccessfulFingerprintRef.current = generateFingerprintRef.current;
      setSettingsChanged(false);
      generateInFlightRef.current = false;
    } else if (!isTerminalManualStatus(next.status)) {
      setPhase("generating");
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
      const next = await reportsApi.getRunStatus(runId, REPORT_SLUG);
      applyRunState(next);
      if (isTerminalManualStatus(next.status)) {
        stopPolling();
      }
    } catch (err) {
      if (isAbortError(err)) return;
      stopPolling();
      setStatus("error");
      setManualStatus("Failed");
      setPhase("failed");
      setErrorMessage(err instanceof Error ? err.message : "Failed to poll run status");
      generateInFlightRef.current = false;
    }
  }, [applyRunState, stopPolling]);

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

  useEffect(() => {
    if (phase === "generating" || phase === "saving") return;
    if (
      lastSuccessfulFingerprintRef.current &&
      currentFingerprint !== lastSuccessfulFingerprintRef.current
    ) {
      setSettingsChanged(true);
      if (phase === "generated") {
        setPhase("unsaved");
        setRunState(null);
        setPreviewData([]);
        setPreviewColumns([]);
        setStatus("idle");
        setManualStatus("Waiting");
      }
    }
  }, [currentFingerprint, phase]);

  const handleGenerate = useCallback(async () => {
    const validationError = validateSectionSelections(sectionStates);
    if (validationError) {
      setErrorMessage(validationError);
      setPhase("failed");
      setStatus("error");
      return;
    }

    if (generateInFlightRef.current || status === "processing") {
      if (runIdRef.current) startPolling(runIdRef.current);
      return;
    }

    generateInFlightRef.current = true;
    generateFingerprintRef.current = currentFingerprint;
    setStatus("processing");
    setManualStatus("Extracting");
    setPhase("generating");
    setErrorMessage(null);
    setSettingsChanged(false);
    setPreviewData([]);
    setPreviewColumns([]);
    setRunState(null);

    const sections = buildSectionsPayload(sectionStates);
    const unionIds = unionColumnIds(sectionStates);
    const requestedFormats = resolveRequestedFormats(exportFormat);

    try {
      const response = await reportsApi.generate(REPORT_SLUG, {
        date_from: dateFrom,
        date_to: dateTo,
        sections,
        selected_column_ids: unionIds,
        column_order: unionIds,
        export_format: resolveApiExportFormat(exportFormat),
        requested_formats: requestedFormats,
        configuration_source: "manual_snapshot",
      });
      startPolling(response.run_id);
    } catch (err) {
      generateInFlightRef.current = false;
      setStatus("error");
      setManualStatus("Failed");
      setPhase("failed");
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
    sectionStates,
    dateFrom,
    dateTo,
    exportFormat,
    currentFingerprint,
    startPolling,
    status,
  ]);

  const handleSaveConfiguration = useCallback(async () => {
    setPhase("saving");
    const sections = buildSectionsPayload(sectionStates);
    const unionIds = unionColumnIds(sectionStates);
    try {
      await reportsApi.saveConfig(REPORT_SLUG, {
        selected_column_ids: unionIds,
        column_order: unionIds,
        export_format: resolveApiExportFormat(exportFormat),
        config_overrides: {
          requested_formats: resolveRequestedFormats(exportFormat),
        },
        sections,
        ...(defaultSections && Object.keys(defaultSections).length > 0
          ? { default_sections: defaultSections }
          : {}),
        date_from: dateFrom,
        date_to: dateTo,
      });
      setPhase(settingsChanged ? "unsaved" : phase === "generated" ? "generated" : "idle");
    } catch (err) {
      setPhase("failed");
      throw err;
    }
  }, [sectionStates, defaultSections, exportFormat, dateFrom, dateTo, settingsChanged, phase]);

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
    lastSuccessfulFingerprintRef.current = null;
    setRunState(null);
    setPreviewData([]);
    setPreviewColumns([]);
    setStatus("idle");
    setManualStatus("Waiting");
    setPhase("idle");
    setErrorMessage(null);
    setSettingsChanged(false);
  }, [stopPolling]);

  const showPdfActions = exportFormat === "pdf" || exportFormat === "both";
  const showExcelActions = exportFormat === "xlsx" || exportFormat === "both";

  return {
    status,
    manualStatus,
    phase,
    runState,
    previewData,
    previewColumns,
    errorMessage,
    settingsChanged,
    handleGenerate,
    handleSaveConfiguration,
    handleDownloadExcel,
    handleDownloadPdf,
    handlePreviewPdf,
    resetGeneration,
    canDownload: runState ? canDownloadManualStatus(runState) : false,
    canDownloadExcel: runState ? canDownloadExcel(runState) : false,
    canDownloadPdf: runState ? canDownloadPdf(runState) : false,
    canPreviewPdf: runState ? canPreviewPdf(runState) : false,
    showPdfActions,
    showExcelActions,
    dualOutputMode: true,
    exportFormat,
  };
}
