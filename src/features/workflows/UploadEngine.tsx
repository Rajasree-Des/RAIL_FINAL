import { useRef, useState, type DragEvent } from "react";
import { FileSpreadsheet, Trash2, Upload, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import type { UploadedFileRecord } from "@/types/workflow";

type UploadEngineProps = {
  acceptedFiles: string[];
  files: UploadedFileRecord[];
  onFilesSelected: (files: FileList) => void;
  onRemoveFile: (id: string) => void;
  multiple?: boolean;
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTimestamp(date: Date): string {
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function createFileRecord(file: File): UploadedFileRecord {
  return {
    id: crypto.randomUUID(),
    name: file.name,
    size: formatFileSize(file.size),
    uploadedAt: formatTimestamp(new Date()),
  };
}

export function UploadEngine({
  acceptedFiles,
  files,
  onFilesSelected,
  onRemoveFile,
  multiple = false,
}: UploadEngineProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    onFilesSelected(fileList);
  }

  function handleDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setIsDragging(false);
    handleFiles(event.dataTransfer.files);
  }

  return (
    <div className="space-y-4">
      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        accept={acceptedFiles.join(",")}
        multiple={multiple}
        aria-label="Upload spreadsheet files"
        onChange={(event) => {
          handleFiles(event.target.files);
          event.target.value = "";
        }}
      />

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`flex w-full flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${
          isDragging
            ? "border-primary/40 bg-primary/5"
            : "border-rail-line bg-white hover:border-slate-300 hover:bg-slate-50"
        }`}
        aria-describedby="upload-help"
      >
        <div
          className={`mb-3 flex h-10 w-10 items-center justify-center rounded-full ${
            isDragging ? "bg-primary/10 text-primary" : "bg-slate-100 text-slate-500"
          }`}
          aria-hidden="true"
        >
          <Upload size={20} />
        </div>
        <span className="text-sm font-medium text-slate-700">
          Drop files here or click to browse
        </span>
        <span id="upload-help" className="mt-1 text-xs text-slate-500">
          Accepted formats: {acceptedFiles.join(", ")}
        </span>
      </button>

      {files.length > 0 ? (
        <div className="space-y-2" role="list" aria-label="Uploaded files">
          {files.map((file) => (
            <div
              key={file.id}
              className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-4"
              role="listitem"
            >
              <div className="flex min-w-0 items-center gap-3">
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-green-50"
                  aria-hidden="true"
                >
                  <FileSpreadsheet size={20} className="text-green-600" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-900">
                    {file.name}
                  </p>
                  <p className="flex items-center gap-2 text-xs text-slate-500">
                    <span>{file.size}</span>
                    <span aria-hidden="true">·</span>
                    <span>{file.uploadedAt}</span>
                    <CheckCircle2 size={14} className="text-green-500" aria-label="Upload complete" />
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Remove ${file.name}`}
                onClick={() => onRemoveFile(file.id)}
              >
                <Trash2 size={16} className="text-slate-400" />
              </Button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
