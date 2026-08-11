import { Link } from "react-router-dom";
import { CheckCircle2, Download, Eye, FileSpreadsheet, FileText } from "lucide-react";
import { useCallback, useState } from "react";
import { automationApi } from "@/api/automation";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import type { AutomationCompletionSummary } from "@/features/automation/types/automation";
import { formatDuration } from "@/features/automation/utils/display";

export interface AutomationCompletionSummaryProps {
  summary: AutomationCompletionSummary;
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export function AutomationCompletionSummaryCard({ summary }: AutomationCompletionSummaryProps) {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onDownload = useCallback(async (key: string, url: string, fallback: string) => {
    setDownloading(key);
    setError(null);
    try {
      const { blob, filename } = await automationApi.downloadBlob(url, fallback);
      triggerBlobDownload(blob, filename || fallback);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(null);
    }
  }, []);

  const downloads = summary.reportDownloads ?? [];
  const reviewHref = summary.runId
    ? `/reports?run_id=${encodeURIComponent(summary.runId)}`
    : "/reports";

  return (
    <Card className="border-rail-line shadow-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <CheckCircle2 className="h-5 w-5 text-green-600" />
          Reports ready
        </CardTitle>
        <CardDescription>Today&apos;s reports have been generated successfully.</CardDescription>
      </CardHeader>
      <CardBody className="space-y-6">
        <ul className="space-y-3 text-sm text-slate-700">
          <li className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            Reports Generated ({summary.reportsGenerated})
          </li>
          <li className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            Dashboard Updated
          </li>
          <li className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            Reports Ready
          </li>
        </ul>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        {downloads.length > 0 ? (
          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-800">Outputs</p>
            <ul className="space-y-2">
              {downloads.map((item) => {
                const pdfUrl = item.pdfDownloadUrl;
                const canPdf = Boolean(pdfUrl);
                return (
                  <li
                    key={item.slug}
                    className="flex flex-wrap items-center justify-between gap-2 text-sm"
                  >
                    <span className="text-slate-700">{item.datasetKey || item.slug}</span>
                    <div className="flex flex-wrap gap-2">
                      {item.pdfPreviewUrl ? (
                        <Button asChild type="button" variant="secondary" size="sm">
                          <a
                            href={
                              item.pdfPreviewUrl.startsWith("http")
                                ? item.pdfPreviewUrl
                                : item.pdfPreviewUrl
                            }
                            target="_blank"
                            rel="noreferrer"
                          >
                            <Eye className="mr-1 h-3.5 w-3.5" />
                            Preview PDF
                          </a>
                        </Button>
                      ) : null}
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={!canPdf || downloading === `${item.slug}-pdf`}
                        onClick={() =>
                          void onDownload(`${item.slug}-pdf`, pdfUrl, `${item.slug}.pdf`)
                        }
                      >
                        <Download className="mr-1 h-3.5 w-3.5" />
                        {downloading === `${item.slug}-pdf` ? "…" : "PDF"}
                      </Button>
                      {item.excelDownloadUrl ? (
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          disabled={downloading === `${item.slug}-xlsx`}
                          onClick={() =>
                            void onDownload(
                              `${item.slug}-xlsx`,
                              item.excelDownloadUrl!,
                              `${item.slug}.xlsx`,
                            )
                          }
                        >
                          <Download className="mr-1 h-3.5 w-3.5" />
                          {downloading === `${item.slug}-xlsx` ? "…" : "Excel"}
                        </Button>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}

        {summary.downloadPdfAllUrl || summary.downloadExcelAllUrl ? (
          <div className="flex flex-wrap gap-2">
            {summary.downloadPdfAllUrl ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={downloading === "pdf-all"}
                onClick={() =>
                  void onDownload(
                    "pdf-all",
                    summary.downloadPdfAllUrl!,
                    "RailMadad_Report.pdf",
                  )
                }
              >
                <FileText className="mr-1 h-3.5 w-3.5" />
                {downloading === "pdf-all" ? "…" : "Download Complete PDF"}
              </Button>
            ) : null}
            {summary.downloadExcelAllUrl ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={downloading === "excel-all"}
                onClick={() =>
                  void onDownload(
                    "excel-all",
                    summary.downloadExcelAllUrl!,
                    "RailMadad_Report.xlsx",
                  )
                }
              >
                <FileSpreadsheet className="mr-1 h-3.5 w-3.5" />
                {downloading === "excel-all" ? "…" : "Download Complete Excel"}
              </Button>
            ) : null}
          </div>
        ) : null}

        <p className="text-xs text-slate-500">
          Completed in {formatDuration(summary.executionTimeMs)}
        </p>
        <div className="flex flex-wrap gap-2">
          <Button asChild>
            <Link to={reviewHref}>
              <Eye className="mr-1 h-4 w-4" />
              Review / Download
            </Link>
          </Button>
          <Button asChild variant="secondary">
            <Link
              to={
                summary.runId
                  ? `/daily-summary?run_id=${encodeURIComponent(summary.runId)}`
                  : "/daily-summary"
              }
            >
              Daily Summary
            </Link>
          </Button>
          <Button asChild variant="secondary">
            <Link to="/dashboard">View Dashboard</Link>
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}
