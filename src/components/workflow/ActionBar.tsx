import { Play, RotateCcw, Download, Save } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface ActionBarProps {
  onGenerate?: () => void;
  onReset?: () => void;
  onDownload?: () => void;
  onSave?: () => void;
  generateDisabled?: boolean;
  resetDisabled?: boolean;
  downloadDisabled?: boolean;
  isProcessing?: boolean;
  showDownload?: boolean;
}

export function ActionBar({
  onGenerate,
  onReset,
  onDownload,
  onSave,
  generateDisabled = false,
  resetDisabled = false,
  downloadDisabled = true,
  isProcessing = false,
  showDownload = true,
}: ActionBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-rail-line bg-white p-4 shadow-card transition-all duration-200 hover:shadow-premium">
      <Button variant="primary" onClick={onGenerate} disabled={generateDisabled || isProcessing}>
        <Play className="mr-2 h-4 w-4" />
        {isProcessing ? "Generating…" : "Generate Report"}
      </Button>
      {onSave && (
        <Button variant="secondary" onClick={onSave} disabled={isProcessing}>
          <Save className="mr-2 h-4 w-4" />
          Save Configuration
        </Button>
      )}
      <Button variant="secondary" onClick={onReset} disabled={resetDisabled || isProcessing}>
        <RotateCcw className="mr-2 h-4 w-4" />
        Reset
      </Button>
      <div className="flex-1" />
      {showDownload && (
        <Button variant="secondary" onClick={onDownload} disabled={downloadDisabled || isProcessing}>
          <Download className="mr-2 h-4 w-4" />
          Download
        </Button>
      )}
    </div>
  );
}
