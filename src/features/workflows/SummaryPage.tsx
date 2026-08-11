import { useState } from "react";
import { Copy, Download, FileCheck, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { Textarea } from "@/components/ui/Textarea";
import { ActionBar } from "@/components/workflow/ActionBar";
import { useSummaryGeneration } from "@/features/workflows/hooks/useSummaryGeneration";
import type { SummaryType } from "@/api/summary";

const OUTPUT_TABS: SummaryType[] = [
  "executive",
  "whatsapp",
  "email",
  "daily_highlights",
  "key_observations",
];

export function SummaryPage() {
  const [showSuccess, setShowSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<SummaryType>("executive");

  const {
    reportOptions,
    selected,
    completedReports,
    generatedSummary,
    isGenerating,
    templates,
    selectedTemplateId,
    setSelectedTemplateId,
    selectedSummaryType,
    setSelectedSummaryType,
    summaryTypeLabels,
    toggleReport,
    handleGenerate,
    handleRegenerate,
    handleReset,
    handleCopy,
    handleDownload,
    handleDownloadAll,
  } = useSummaryGeneration();

  async function onGenerate() {
    await handleGenerate();
    setShowSuccess(true);
    setTimeout(() => setShowSuccess(false), 3000);
  }

  function getContent(type: SummaryType): string {
    if (!generatedSummary) return "";
    const map: Record<SummaryType, string> = {
      executive: generatedSummary.executive,
      whatsapp: generatedSummary.whatsapp,
      email: generatedSummary.email,
      daily_highlights: generatedSummary.dailyHighlights,
      key_observations: generatedSummary.keyObservations,
    };
    return map[type];
  }

  const completedCount = Array.from(completedReports).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Summary Generation"
        description="Generate AI-powered summaries from processed report data"
      />

      {showSuccess && generatedSummary ? (
        <Alert variant="success" title="Summary generated successfully">
          Your summaries are ready for review, copy, and download.
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="prompt-template">Prompt Template (optional)</Label>
              <Select
                id="prompt-template"
                value={selectedTemplateId}
                onChange={(e) => setSelectedTemplateId(e.target.value)}
              >
                <option value="">Use default templates (all types)</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({summaryTypeLabels[t.summary_type as SummaryType]})
                  </option>
                ))}
              </Select>
            </div>
            {selectedTemplateId ? (
              <div className="space-y-2">
                <Label htmlFor="summary-type">Summary Type</Label>
                <Select
                  id="summary-type"
                  value={selectedSummaryType}
                  onChange={(e) =>
                    setSelectedSummaryType(e.target.value as SummaryType)
                  }
                >
                  {Object.entries(summaryTypeLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </Select>
              </div>
            ) : null}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Completed Reports</CardTitle>
          <p className="text-sm text-slate-500">
            {completedCount} of {reportOptions.length} reports completed
          </p>
        </CardHeader>
        <CardBody>
          {completedCount === 0 ? (
            <Alert variant="info" title="No reports completed yet">
              Complete other workflow reports first to generate a summary.
            </Alert>
          ) : (
            <div className="space-y-2" role="group" aria-label="Select reports">
              {reportOptions.map((option) => {
                const isAvailable = completedReports.has(option.id);
                return (
                  <Checkbox
                    key={option.id}
                    id={option.id}
                    checked={selected.includes(option.id)}
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
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Generated Summaries</CardTitle>
        </CardHeader>
        <CardBody>
          {isGenerating ? (
            <div className="flex justify-center py-12">
              <Spinner size="lg" />
            </div>
          ) : generatedSummary ? (
            <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as SummaryType)}>
              <TabsList>
                {OUTPUT_TABS.map((key) => (
                  <TabsTrigger key={key} value={key}>
                    {summaryTypeLabels[key]}
                  </TabsTrigger>
                ))}
              </TabsList>
              {OUTPUT_TABS.map((key) => (
                <TabsContent key={key} value={key} className="mt-4 space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleCopy(getContent(key))}
                    >
                      <Copy className="mr-1 h-4 w-4" />
                      Copy
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        handleDownload(getContent(key), `${key}-summary.txt`)
                      }
                    >
                      <Download className="mr-1 h-4 w-4" />
                      Download
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRegenerate(key)}
                      disabled={isGenerating}
                    >
                      <RefreshCw className="mr-1 h-4 w-4" />
                      Regenerate
                    </Button>
                  </div>
                  <Textarea
                    readOnly
                    value={getContent(key)}
                    className="min-h-48 bg-slate-50 font-mono text-sm"
                    aria-label={`${summaryTypeLabels[key]} content`}
                  />
                </TabsContent>
              ))}
            </Tabs>
          ) : (
            <EmptyState
              icon={FileCheck}
              title="No summary generated"
              description="Select completed reports and click Generate to create AI summaries."
            />
          )}
        </CardBody>
      </Card>

      <ActionBar
        onGenerate={onGenerate}
        onReset={handleReset}
        onDownload={handleDownloadAll}
        isProcessing={isGenerating}
        generateDisabled={selected.length === 0}
        downloadDisabled={!generatedSummary}
      />
    </div>
  );
}
