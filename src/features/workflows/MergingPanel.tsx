import { useMemo, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { OutputViewer } from "@/features/workflows/OutputViewer";
import { SpreadsheetViewer } from "@/features/workflows/SpreadsheetViewer";
import { UploadEngine } from "@/features/workflows/UploadEngine";
import { WorkflowSectionCard } from "@/features/workflows/WorkflowSectionCard";
import { WorkflowActionBar } from "@/features/workflows/components/WorkflowActionBar";
import { useWorkflowActions } from "@/features/workflows/hooks/useWorkflowActions";
import type { WorkflowDefinition } from "@/types/workflow";

type MergingPanelProps = {
  workflow: WorkflowDefinition;
};

export function MergingPanel({ workflow }: MergingPanelProps) {
  const columns = workflow.previewColumns ?? [];
  const [showSuccess, setShowSuccess] = useState(false);

  const {
    files,
    previewData,
    isGenerating,
    hasGenerated,
    handleFilesSelected,
    handleRemoveFile,
    handleGenerate,
    handleReset,
    handleDownload,
  } = useWorkflowActions({ workflow, columns, multiple: true });

  const displayData = useMemo(
    () => (hasGenerated ? previewData : []),
    [hasGenerated, previewData],
  );

  function onGenerate() {
    handleGenerate();
    setShowSuccess(true);
    setTimeout(() => setShowSuccess(false), 3000);
  }

  function onReset() {
    handleReset();
    setShowSuccess(false);
  }

  return (
    <div className="space-y-6">
      {showSuccess && hasGenerated ? (
        <Alert variant="success" title="Files merged successfully">
          {files.length} files have been merged. Ready for download.
        </Alert>
      ) : null}

      <WorkflowSectionCard
        id="upload"
        title="Upload"
        description="Upload multiple spreadsheets to merge"
      >
        <UploadEngine
          acceptedFiles={workflow.acceptedFiles ?? [".xlsx", ".xls", ".csv"]}
          files={files}
          multiple
          onFilesSelected={handleFilesSelected}
          onRemoveFile={handleRemoveFile}
        />
        {files.length > 1 && !hasGenerated ? (
          <div className="mt-4">
            <Button
              variant="primary"
              onClick={onGenerate}
              disabled={isGenerating}
            >
              {isGenerating ? "Merging..." : "Merge Files"}
            </Button>
          </div>
        ) : null}
      </WorkflowSectionCard>

      <WorkflowSectionCard
        id="preview"
        title="Preview"
        description="Preview merged data"
      >
        <SpreadsheetViewer
          columns={columns}
          data={displayData}
          emptyMessage={
            files.length === 0
              ? "Upload spreadsheets to preview merged data."
              : "Click Merge to combine uploaded files."
          }
        />
      </WorkflowSectionCard>

      <WorkflowSectionCard
        id="output"
        title="Output"
        description="Download merged dataset"
      >
        <OutputViewer
          tabs={["Export"]}
          workflowName={workflow.name}
          previewColumns={columns}
          previewData={displayData}
          onDownload={handleDownload}
        />
      </WorkflowSectionCard>

      <WorkflowActionBar
        onGenerate={onGenerate}
        onReset={onReset}
        onDownload={() => handleDownload("excel")}
        isGenerating={isGenerating}
        canGenerate={files.length >= 2}
        canDownload={hasGenerated}
      />
    </div>
  );
}
