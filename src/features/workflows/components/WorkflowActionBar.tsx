import { Download, RefreshCw, Copy, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";

type WorkflowActionBarProps = {
  onGenerate: () => void;
  onReset: () => void;
  onDownload: () => void;
  onCopy?: () => void;
  isGenerating?: boolean;
  canGenerate?: boolean;
  canDownload?: boolean;
  generateLabel?: string;
};

export function WorkflowActionBar({
  onGenerate,
  onReset,
  onDownload,
  onCopy,
  isGenerating = false,
  canGenerate = true,
  canDownload = false,
  generateLabel = "Generate",
}: WorkflowActionBarProps) {
  return (
    <div
      className="flex flex-col gap-3 pt-2 sm:flex-row"
      role="group"
      aria-label="Workflow actions"
    >
      <Button
        variant="primary"
        onClick={onGenerate}
        disabled={!canGenerate || isGenerating}
        aria-busy={isGenerating}
      >
        {isGenerating ? (
          <Loader2 size={16} className="animate-spin" aria-hidden="true" />
        ) : (
          <Download size={16} aria-hidden="true" />
        )}
        {isGenerating ? "Generating..." : generateLabel}
      </Button>

      <Button variant="secondary" onClick={onReset}>
        <RefreshCw size={16} aria-hidden="true" />
        Reset
      </Button>

      <Button variant="secondary" onClick={onDownload} disabled={!canDownload}>
        <Download size={16} aria-hidden="true" />
        Download
      </Button>

      {onCopy ? (
        <Button variant="ghost" onClick={onCopy}>
          <Copy size={16} aria-hidden="true" />
          Copy
        </Button>
      ) : null}
    </div>
  );
}
