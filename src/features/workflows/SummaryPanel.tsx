import { useState } from "react";
import { Copy, FileCheck } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Textarea } from "@/components/ui/Textarea";
import { EmptyState } from "@/components/ui/EmptyState";
import { WorkflowSectionCard } from "@/features/workflows/WorkflowSectionCard";
import { WorkflowActionBar } from "@/features/workflows/components/WorkflowActionBar";
import { useSummaryGeneration } from "@/features/workflows/hooks/useSummaryGeneration";
import type { WorkflowDefinition } from "@/types/workflow";

type SummaryPanelProps = {
  workflow: WorkflowDefinition;
};

export function SummaryPanel({ workflow }: SummaryPanelProps) {
  const [showSuccess, setShowSuccess] = useState(false);

  const {
    reportOptions,
    selected,
    completedReports,
    generatedSummary,
    isGenerating,
    toggleReport,
    handleGenerate,
    handleReset,
    handleCopy,
    handleDownload,
    handleDownloadAll,
  } = useSummaryGeneration();

  function onGenerate() {
    handleGenerate();
    setShowSuccess(true);
    setTimeout(() => setShowSuccess(false), 3000);
  }

  function onReset() {
    handleReset();
    setShowSuccess(false);
  }

  const completedCount = Array.from(completedReports).length;

  return (
    <div className="space-y-6">
      {showSuccess && generatedSummary ? (
        <Alert variant="success" title="Summary generated successfully">
          Your official summary is ready for download and sharing.
        </Alert>
      ) : null}

      <WorkflowSectionCard
        id="reports"
        title="Completed Reports"
        description={`${completedCount} of ${reportOptions.length} reports completed`}
      >
        {completedCount === 0 ? (
          <Alert variant="info" title="No reports completed yet">
            Complete other workflow reports first to generate a summary.
          </Alert>
        ) : (
          <div className="space-y-2" role="group" aria-label="Select reports to include">
            {reportOptions.map((option) => {
              const isAvailable = completedReports.has(option.id);
              const isChecked = selected.includes(option.id);
              return (
                <Checkbox
                  key={option.id}
                  id={option.id}
                  checked={isChecked}
                  disabled={!isAvailable}
                  onChange={() => toggleReport(option.id)}
                  label={
                    <>
                      {option.label}
                      {!isAvailable ? (
                        <span className="ml-auto text-xs text-slate-400">
                          Not completed
                        </span>
                      ) : null}
                    </>
                  }
                />
              );
            })}
          </div>
        )}
      </WorkflowSectionCard>

      <WorkflowSectionCard
        id="output"
        title="Output"
        description="Generated summary content"
      >
        {generatedSummary ? (
          <div className="space-y-6">
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">
                AI Summary Preview
              </label>
              <Textarea
                readOnly
                value={generatedSummary.executive}
                className="min-h-28 bg-slate-50"
                aria-label="AI generated summary"
              />
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">
                  WhatsApp Message
                </label>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleCopy(generatedSummary.whatsapp)}
                  aria-label="Copy WhatsApp message"
                >
                  <Copy size={14} aria-hidden="true" />
                  Copy
                </Button>
              </div>
              <Textarea
                readOnly
                value={generatedSummary.whatsapp}
                className="bg-slate-50"
                aria-label="WhatsApp message content"
              />
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">
                  Email Body
                </label>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleCopy(generatedSummary.email)}
                  aria-label="Copy email body"
                >
                  <Copy size={14} aria-hidden="true" />
                  Copy
                </Button>
              </div>
              <Textarea
                readOnly
                value={generatedSummary.email}
                className="min-h-28 bg-slate-50"
                aria-label="Email body content"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">
                PDF Preview
              </label>
              <div className="rounded-lg border border-slate-200 bg-white p-6">
                <p className="whitespace-pre-line text-sm leading-7 text-slate-700">
                  {generatedSummary.dailyHighlights || generatedSummary.keyObservations}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <EmptyState
            icon={<FileCheck size={24} />}
            title="No summary generated"
            description={`Select completed reports and click Generate to create the official ${workflow.name.toLowerCase()}.`}
          />
        )}
      </WorkflowSectionCard>

      <WorkflowActionBar
        onGenerate={onGenerate}
        onReset={onReset}
        onDownload={() => handleDownloadAll()}
        onCopy={
          generatedSummary
            ? () => handleCopy(generatedSummary.whatsapp)
            : undefined
        }
        isGenerating={isGenerating}
        canGenerate={selected.length > 0}
        canDownload={!!generatedSummary}
        generateLabel="Generate Summary"
      />
    </div>
  );
}
