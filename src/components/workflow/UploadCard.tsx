import React, { useCallback, useState } from "react";
import { Upload, X, CheckCircle2 } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { cn } from "@/utils/cn";

interface UploadedFile {
  name: string;
  size: number;
  type: string;
}

interface UploadCardProps {
  title?: string;
  description?: string;
  acceptedFormats?: string[];
  maxSizeMB?: number;
  onFileSelect?: (file: File) => void;
  onFileRemove?: () => void;
  disabled?: boolean;
}

export function UploadCard({
  title = "Upload File",
  description = "Upload your Excel or CSV file to process",
  acceptedFormats = [".xlsx", ".xls", ".csv"],
  maxSizeMB = 50,
  onFileSelect,
  onFileRemove,
  disabled = false,
}: UploadCardProps) {
  const [file, setFile] = useState<UploadedFile | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const handleFile = useCallback(
    (selectedFile: File) => {
      setFile({
        name: selectedFile.name,
        size: selectedFile.size,
        type: selectedFile.type,
      });
      onFileSelect?.(selectedFile);
    },
    [onFileSelect],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled) return;

      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) {
        handleFile(droppedFile);
      }
    },
    [disabled, handleFile],
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled) setIsDragging(true);
    },
    [disabled],
  );

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        handleFile(selectedFile);
      }
    },
    [handleFile],
  );

  const handleRemove = useCallback(() => {
    setFile(null);
    onFileRemove?.();
  }, [onFileRemove]);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
      </CardHeader>
      <CardBody>
        {file ? (
          <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium text-slate-900">{file.name}</p>
              <p className="text-xs text-slate-500">{formatFileSize(file.size)}</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRemove}
              disabled={disabled}
              aria-label="Remove file"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <label
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 transition-colors",
              isDragging
                ? "border-primary bg-primary/5"
                : "border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-slate-100",
              disabled && "cursor-not-allowed opacity-50",
            )}
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-200">
              <Upload className="h-6 w-6 text-slate-500" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-slate-700">
                Drop your file here or <span className="text-primary">browse</span>
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Accepted: {acceptedFormats.join(", ")} (Max {maxSizeMB}MB)
              </p>
            </div>
            <input
              type="file"
              accept={acceptedFormats.join(",")}
              onChange={handleInputChange}
              disabled={disabled}
              className="sr-only"
            />
          </label>
        )}
      </CardBody>
    </Card>
  );
}
