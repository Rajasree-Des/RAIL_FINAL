import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Download,
  Eye,
  FileSpreadsheet,
  RefreshCw,
  FileText,
} from "lucide-react";
import {
  automationApi,
  type AutomationArtifact,
  type AutomationRunDetail,
  type CdpRunSummary,
  type ReportResult,
} from "@/api/automation";
import { dailySummaryApi, type DailySummary } from "@/api/dailySummary";
import { PageHeader } from "@/components/PageHeader";
import { PdfPreviewModal } from "@/components/PdfPreviewModal";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn } from "@/utils/cn";
import { formatDateTime12h } from "@/utils/datetime";
import { getReportDisplayName, getReportDownloadName } from "@/utils/reportDisplayNames";

const LAST_RUN_KEY = "railmadad_last_run_id";

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

export function GeneratedReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const runIdFromUrl = searchParams.get("run_id");
  const [runs, setRuns] = useState<CdpRunSummary[]>([]);
  const [run, setRun] = useState<AutomationRunDetail | null>(null);
  const [artifacts, setArtifacts] = useState<AutomationArtifact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewApiUrl, setPreviewApiUrl] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState<string>("PDF Review");
  const [busy, setBusy] = useState<string | null>(null);
  const [dailySummary, setDailySummary] = useState<DailySummary | null>(null);

  const selectedRunId = runIdFromUrl || localStorage.getItem(LAST_RUN_KEY);

  const loadRuns = useCallback(async () => {
    try {
      const list = await automationApi.listCdpRuns(30);
      setRuns(list);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const loadRun = useCallback(async (runId: string) => {
    setLoading(true);
    setError(null);
    try {
      const detail = await automationApi.getRun(runId);
      const arts = await automationApi.getRunArtifacts(runId);
      setRun(detail);
      setArtifacts(arts);
      localStorage.setItem(LAST_RUN_KEY, runId);
      setSearchParams({ run_id: runId }, { replace: true });
      try {
        const summary = await dailySummaryApi.getForRun(runId);
        setDailySummary(summary);
      } catch {
        setDailySummary(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load run");
      setRun(null);
      setArtifacts([]);
      setDailySummary(null);
    } finally {
      setLoading(false);
    }
  }, [setSearchParams]);

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    if (selectedRunId) {
      void loadRun(selectedRunId);
    }
  }, [selectedRunId, loadRun]);

  const artifactsBySlug = useMemo(() => {
    const map = new Map<string, { pdf?: AutomationArtifact; excel?: AutomationArtifact }>();
    const sorted = [...artifacts].sort((a, b) => {
      const aTime = a.created_at ? Date.parse(a.created_at) : 0;
      const bTime = b.created_at ? Date.parse(b.created_at) : 0;
      return bTime - aTime;
    });
    for (const art of sorted) {
      const slug = art.report_slug || art.report_name || "unknown";
      const entry = map.get(slug) ?? {};
      if (art.file_type === "pdf" && !entry.pdf) entry.pdf = art;
      if (art.file_type === "excel" && !entry.excel) entry.excel = art;
      map.set(slug, entry);
    }
    return map;
  }, [artifacts]);

  const reports: ReportResult[] = run?.reports?.length
    ? run.reports
    : Array.from(artifactsBySlug.keys()).map((slug) => ({
        slug,
        status: "success" as const,
      }));

  const onDownload = async (url: string | null | undefined, filename: string, key: string) => {
    if (!url) {
      setError("File is not available yet");
      return;
    }
    setBusy(key);
    setError(null);
    try {
      const { blob, filename: serverName } = await automationApi.downloadBlob(url, filename);
      triggerBlobDownload(blob, serverName || filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setBusy(null);
    }
  };

  const onRetry = async (slug: string) => {
    setBusy(`retry-${slug}`);
    setError(null);
    try {
      const result = await automationApi.start({ report_slugs: [slug] });
      if (result.run_id) {
        await loadRun(result.run_id);
        await loadRuns();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retry failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Run Results"
        description="Review and download Excel/PDF artifacts from automation runs."
      />

      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <Card className="h-fit border-rail-line">
          <CardHeader>
            <CardTitle className="text-sm">Previous runs</CardTitle>
            <CardDescription>Select a run to review</CardDescription>
          </CardHeader>
          <CardBody className="space-y-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="w-full"
              onClick={() => void loadRuns()}
            >
              <RefreshCw className="mr-1 h-3.5 w-3.5" />
              Refresh
            </Button>
            {runs.length === 0 ? (
              <p className="text-xs text-slate-500">No CDP runs yet.</p>
            ) : (
              <ul className="max-h-[28rem] space-y-1 overflow-auto">
                {runs.map((item) => (
                  <li key={item.run_id}>
                    <button
                      type="button"
                      className={cn(
                        "w-full rounded-md px-2 py-2 text-left text-xs",
                        selectedRunId === item.run_id
                          ? "bg-slate-900 text-white"
                          : "hover:bg-slate-100 text-slate-700",
                      )}
                      onClick={() => void loadRun(item.run_id)}
                    >
                      <div className="font-medium">{item.status}</div>
                      <div className="opacity-80">
                        {item.started_at
                          ? formatDateTime12h(item.started_at)
                          : item.run_id.slice(0, 8)}
                      </div>
                      <div className="opacity-70">
                        ok {item.success_count} / fail {item.failure_count}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <div className="space-y-4">
          {error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          {loading ? <p className="text-sm text-slate-500">Loading run…</p> : null}

          {!loading && !run ? (
            <Card>
              <CardBody className="space-y-3 py-10 text-center">
                <p className="text-sm text-slate-600">
                  No run selected. Start automation, then return here to review outputs.
                </p>
                <Button asChild>
                  <Link to="/automation">Go to Automation</Link>
                </Button>
              </CardBody>
            </Card>
          ) : null}

          {run ? (
            <>
              <Card className="border-rail-line">
                <CardHeader className="flex flex-row items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">Run {run.run_id.slice(0, 8)}…</CardTitle>
                    <CardDescription>
                      Status: {run.status}
                      {run.total_duration_seconds != null
                        ? ` · ${Math.round(run.total_duration_seconds / 60)}m ${Math.round(
                            run.total_duration_seconds % 60,
                          )}s`
                        : ""}
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={
                        !(run.download_pdf_all_url || run.run_id) || busy === "pdf-all"
                      }
                      onClick={() =>
                        void onDownload(
                          run.download_pdf_all_url ||
                            automationApi.downloadPdfAllUrl(run.run_id),
                          "RailMadad_Report.pdf",
                          "pdf-all",
                        )
                      }
                    >
                      <FileText className="mr-1 h-3.5 w-3.5" />
                      {busy === "pdf-all" ? "…" : "Download Complete PDF"}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={
                        !(run.download_excel_all_url || run.run_id) || busy === "excel-all"
                      }
                      onClick={() =>
                        void onDownload(
                          run.download_excel_all_url ||
                            automationApi.downloadExcelAllUrl(run.run_id),
                          "RailMadad_Report.xlsx",
                          "excel-all",
                        )
                      }
                    >
                      <FileSpreadsheet className="mr-1 h-3.5 w-3.5" />
                      {busy === "excel-all" ? "…" : "Download Complete Excel"}
                    </Button>
                  </div>
                </CardHeader>
              </Card>

              <div className="grid gap-4 md:grid-cols-2">
                {reports.map((report) => {
                  const arts = artifactsBySlug.get(report.slug) ?? {};
                  const previewBase =
                    arts.pdf?.preview_url ||
                    report.pdf_preview_url ||
                    (arts.pdf ? automationApi.artifactPreviewUrl(arts.pdf.id) : null);
                  const preview = previewBase
                    ? automationApi.withCacheBust(previewBase, arts.pdf?.id, run.run_id)
                    : null;
                  const pdfDl =
                    arts.pdf?.status === "ready"
                      ? arts.pdf.download_url ||
                        (arts.pdf ? automationApi.artifactDownloadUrl(arts.pdf.id) : null)
                      : report.pdf_download_url || null;
                  const excelDl =
                    arts.excel?.download_url ||
                    report.excel_download_url ||
                    (arts.excel ? automationApi.artifactDownloadUrl(arts.excel.id) : null);
                  const hasCurrentPdfUrl = Boolean(preview || pdfDl || report.pdf_download_url);
                  const hasCurrentExcelUrl = Boolean(excelDl);
                  const pdfReady =
                    arts.pdf?.status === "ready" || Boolean(report.pdf_download_url);
                  const excelReady =
                    arts.excel?.status === "ready" || Boolean(report.excel_download_url);
                  const failed = report.status === "failed";
                  const terminalPartial = report.status === "partial_success";
                  // Terminal success must never show deferred/stale pending error text.
                  const displayError =
                    report.status === "success" ? null : report.error || null;

                  return (
                    <Card key={report.slug} className="border-rail-line">
                      <CardHeader className="pb-3">
                        <CardTitle className="text-sm leading-snug break-words">
                          {getReportDisplayName(report.slug)}
                        </CardTitle>
                        <CardDescription>
                          {report.status}
                          {report.row_count != null || report.source_row_count != null
                            ? ` · ${report.row_count ?? report.source_row_count} rows`
                            : ""}
                          {report.duration_seconds != null
                            ? ` · ${report.duration_seconds.toFixed(1)}s`
                            : ""}
                        </CardDescription>
                      </CardHeader>
                      <CardBody className="space-y-3">
                        {displayError ? (
                          <p className="text-xs text-red-600">{displayError}</p>
                        ) : null}
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={!pdfReady || !preview || !hasCurrentPdfUrl}
                            onClick={() => {
                              setPreviewTitle(getReportDisplayName(report.slug));
                              setPreviewApiUrl(preview);
                            }}
                          >
                            <Eye className="mr-1 h-3.5 w-3.5" />
                            Preview PDF
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={!pdfReady || !pdfDl || !hasCurrentPdfUrl || busy === `pdf-${report.slug}`}
                            onClick={() =>
                              void onDownload(
                                pdfDl,
                                `${getReportDownloadName(report.slug)}.pdf`,
                                `pdf-${report.slug}`,
                              )
                            }
                          >
                            <Download className="mr-1 h-3.5 w-3.5" />
                            Download PDF
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={!excelReady || !excelDl || !hasCurrentExcelUrl || busy === `xlsx-${report.slug}`}
                            onClick={() =>
                              void onDownload(
                                excelDl,
                                `${getReportDownloadName(report.slug)}.xlsx`,
                                `xlsx-${report.slug}`,
                              )
                            }
                          >
                            <FileSpreadsheet className="mr-1 h-3.5 w-3.5" />
                            Download Excel
                          </Button>
                          {failed || terminalPartial ? (
                            <Button
                              type="button"
                              size="sm"
                              disabled={busy === `retry-${report.slug}`}
                              onClick={() => void onRetry(report.slug)}
                            >
                              Retry
                            </Button>
                          ) : null}
                        </div>
                      </CardBody>
                    </Card>
                  );
                })}
              </div>

              <Card className="border-rail-line">
                <CardHeader className="flex flex-row items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <FileText size={16} />
                      Daily Summary
                    </CardTitle>
                    <CardDescription>
                      {dailySummary
                        ? `${dailySummary.status} · report date ${dailySummary.report_date || "—"}`
                        : "Not generated yet for this run"}
                    </CardDescription>
                  </div>
                  <Button asChild size="sm" variant="secondary">
                    <Link to={`/daily-summary?run_id=${run.run_id}`}>Open Daily Summary</Link>
                  </Button>
                </CardHeader>
                {dailySummary?.text ? (
                  <CardBody>
                    {dailySummary.missing_reports.length > 0 ? (
                      <p className="mb-2 text-xs text-amber-700">
                        Missing:{" "}
                        {dailySummary.missing_reports
                          .map((slug) => getReportDisplayName(slug))
                          .join(", ")}
                      </p>
                    ) : null}
                    <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-surface p-3 text-xs text-rail-ink font-sans">
                      {dailySummary.text.slice(0, 800)}
                      {dailySummary.text.length > 800 ? "…" : ""}
                    </pre>
                  </CardBody>
                ) : null}
              </Card>
            </>
          ) : null}
        </div>
      </div>

      <PdfPreviewModal
        apiUrl={previewApiUrl}
        title={previewTitle}
        onClose={() => {
          setPreviewApiUrl(null);
          setPreviewTitle("PDF Review");
        }}
      />
    </div>
  );
}
