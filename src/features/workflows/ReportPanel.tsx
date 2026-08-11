import { useMemo, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { OutputViewer } from "@/features/workflows/OutputViewer";
import { SpreadsheetViewer } from "@/features/workflows/SpreadsheetViewer";
import { SettingsRenderer } from "@/features/workflows/SettingsRenderer";
import { UploadEngine } from "@/features/workflows/UploadEngine";
import { WorkflowSectionCard } from "@/features/workflows/WorkflowSectionCard";
import { WorkflowActionBar } from "@/features/workflows/components/WorkflowActionBar";
import { useWorkflowActions } from "@/features/workflows/hooks/useWorkflowActions";
import type { WorkflowDefinition } from "@/types/workflow";

type ReportPanelProps = {
  workflow: WorkflowDefinition;
};

export function ReportPanel({ workflow }: ReportPanelProps) {
  const columns = workflow.previewColumns ?? [];
  const [showSuccess, setShowSuccess] = useState(false);

  const [settings, setSettings] = useState<Record<string, unknown>>(() =>
    Object.fromEntries(
      (workflow.settings ?? []).map((s) => [s.id, s.defaultValue ?? ""]),
    ),
  );

  const {
    files,
    previewData,
    outputData,
    isGenerating,
    hasGenerated,
    handleFilesSelected,
    handleRemoveFile,
    handleGenerate,
    handleReset,
    handleDownload,
  } = useWorkflowActions({ workflow, columns, multiple: false });

  const pdfContent = useMemo(() => {
    const date = settings.reportDate ?? settings.date ?? "selected date";
    const division = settings.division ?? "all divisions";
    return `${workflow.name} report for ${date}. Division: ${division}. This official document summarizes key performance indicators, complaint trends, and recommended actions for railway administration review.`;
  }, [settings, workflow.name]);

  function onGenerate() {
    handleGenerate();
    setShowSuccess(true);
    setTimeout(() => setShowSuccess(false), 3000);
  }

  function onReset() {
    handleReset();
    setShowSuccess(false);
    setSettings(
      Object.fromEntries(
        (workflow.settings ?? []).map((s) => [s.id, s.defaultValue ?? ""]),
      ),
    );
  }

  return (
    <div className="space-y-6">
      {showSuccess && hasGenerated ? (
        <Alert variant="success" title="Report generated successfully">
          Your {workflow.name} report is ready for download.
        </Alert>
      ) : null}

      {workflow.settings && workflow.settings.length > 0 ? (
        <WorkflowSectionCard
          id="settings"
          title="Settings"
          description="Configure report parameters"
        >
          <SettingsRenderer
            settings={workflow.settings}
            values={settings}
            onChange={(id, value) => setSettings((c) => ({ ...c, [id]: value }))}
          />
        </WorkflowSectionCard>
      ) : null}

      <WorkflowSectionCard
        id="upload"
        title="Upload"
        description={workflow.uploadLabel ?? "Upload your data file"}
      >
        <UploadEngine
          acceptedFiles={workflow.acceptedFiles ?? [".xlsx", ".xls", ".csv"]}
          files={files}
          multiple={false}
          onFilesSelected={handleFilesSelected}
          onRemoveFile={() => handleRemoveFile(files[0]?.id ?? "")}
        />
      </WorkflowSectionCard>

      <WorkflowSectionCard
        id="preview"
        title="Preview"
        description="Preview uploaded data before generating"
      >
        <SpreadsheetViewer
          columns={columns}
          data={previewData}
          emptyMessage="Upload a file to preview the data."
        />
      </WorkflowSectionCard>

      <WorkflowSectionCard
        id="output"
        title="Output"
        description="Generated report output"
      >
        <OutputViewer
          tabs={["Spreadsheet", "PDF Preview"]}
          workflowName={workflow.name}
          previewColumns={columns}
          previewData={hasGenerated ? outputData : undefined}
          pdfContent={pdfContent}
          onDownload={handleDownload}
        />
      </WorkflowSectionCard>

      <WorkflowActionBar
        onGenerate={onGenerate}
        onReset={onReset}
        onDownload={() => handleDownload(String(settings.outputFormat ?? "pdf"))}
        isGenerating={isGenerating}
        canGenerate={files.length > 0}
        canDownload={hasGenerated}
      />
    </div>
  );
}
