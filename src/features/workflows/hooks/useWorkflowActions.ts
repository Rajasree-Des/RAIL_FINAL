import { useCallback, useState } from "react";
import type { RowData, SpreadsheetColumn, UploadedFileRecord, WorkflowDefinition } from "@/types/workflow";
import { useWorkflowSession } from "@/context/WorkflowSessionContext";
import { createFileRecord } from "@/features/workflows/UploadEngine";
import { generatePreviewData, generateMergedPreviewData } from "@/features/workflows/SpreadsheetViewer";

type UseWorkflowActionsOptions = {
  workflow: WorkflowDefinition;
  columns: SpreadsheetColumn[];
  multiple?: boolean;
};

type UseWorkflowActionsReturn = {
  files: UploadedFileRecord[];
  previewData: RowData[];
  outputData: RowData[];
  isGenerating: boolean;
  hasGenerated: boolean;
  handleFilesSelected: (fileList: FileList) => void;
  handleRemoveFile: (id: string) => void;
  handleGenerate: () => void;
  handleReset: () => void;
  handleDownload: (format: string) => void;
};

export function useWorkflowActions({
  workflow,
  columns,
  multiple = false,
}: UseWorkflowActionsOptions): UseWorkflowActionsReturn {
  const { markReportComplete } = useWorkflowSession();
  const [files, setFiles] = useState<UploadedFileRecord[]>([]);
  const [previewData, setPreviewData] = useState<RowData[]>([]);
  const [outputData, setOutputData] = useState<RowData[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [hasGenerated, setHasGenerated] = useState(false);

  const handleFilesSelected = useCallback(
    (fileList: FileList) => {
      if (multiple) {
        const newFiles = Array.from(fileList).map(createFileRecord);
        setFiles((current) => [...current, ...newFiles]);
      } else {
        const file = fileList[0];
        if (!file) return;
        const record = createFileRecord(file);
        setFiles([record]);
        setPreviewData(generatePreviewData(columns, 25, file.name));
      }
      setHasGenerated(false);
      setOutputData([]);
    },
    [columns, multiple],
  );

  const handleRemoveFile = useCallback((id: string) => {
    setFiles((current) => current.filter((file) => file.id !== id));
    setPreviewData([]);
    setOutputData([]);
    setHasGenerated(false);
  }, []);

  const handleGenerate = useCallback(() => {
    if (files.length === 0) return;
    setIsGenerating(true);

    window.setTimeout(() => {
      if (multiple) {
        const merged = generateMergedPreviewData(columns, files.map((f) => f.name));
        setOutputData(merged);
        setPreviewData(merged);
      } else {
        const rowCount = workflow.name.includes("Top 25")
          ? 25
          : workflow.name.includes("Top 20")
            ? 20
            : workflow.name.includes("Top 10")
              ? 10
              : 25;
        const generated = generatePreviewData(columns, rowCount);
        setOutputData(generated);
      }
      setHasGenerated(true);
      setIsGenerating(false);

      if (workflow.reportSourceId) {
        markReportComplete(workflow.reportSourceId);
      }
    }, 800);
  }, [files, columns, multiple, workflow, markReportComplete]);

  const handleReset = useCallback(() => {
    setFiles([]);
    setPreviewData([]);
    setOutputData([]);
    setHasGenerated(false);
  }, []);

  const handleDownload = useCallback(
    (format: string) => {
      window.alert(`Downloading ${workflow.name} as ${format.toUpperCase()}...`);
    },
    [workflow.name],
  );

  return {
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
  };
}
