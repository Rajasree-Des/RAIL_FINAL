import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ClipboardCopy,
  Download,
  History,
  RefreshCw,
  FileText,
} from "lucide-react";
import {
  dailySummaryApi,
  type DailySummary,
  type DailySummaryListItem,
} from "@/api/dailySummary";
import { automationApi, type CdpRunSummary } from "@/api/automation";
import { ApiError } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { formatDateTime12h } from "@/utils/datetime";
import { cn } from "@/utils/cn";

const LAST_RUN_KEY = "railmadad_last_run_id";
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type SummaryLoadState = "idle" | "no_summary" | "run_not_found" | "error";

export function DailySummaryPage() {
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const runIdFromUrl = searchParams.get("run_id");
  const [runs, setRuns] = useState<CdpRunSummary[]>([]);
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [previous, setPrevious] = useState<DailySummaryListItem[]>([]);
  const [showPrevious, setShowPrevious] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<SummaryLoadState>("idle");
  const [errorDetail, setErrorDetail] = useState<string | null>(null);
  const loadGenerationRef = useRef(0);

  const selectedRunId = runIdFromUrl || localStorage.getItem(LAST_RUN_KEY);
  const validRunId =
    selectedRunId && UUID_RE.test(selectedRunId) ? selectedRunId : null;
  const selectedRun = runs.find((r) => r.run_id === validRunId);
  const runIsProcessing =
    selectedRun != null &&
    !["completed", "failed", "stopped"].includes(selectedRun.status);

  const loadRuns = useCallback(async () => {
    try {
      const list = await automationApi.listCdpRuns(30);
      setRuns(list);
      if (
        validRunId &&
        !list.some((r) => r.run_id === validRunId) &&
        list.length > 0
      ) {
        const latest = list[0].run_id;
        localStorage.setItem(LAST_RUN_KEY, latest);
        setSearchParams({ run_id: latest }, { replace: true });
      }
    } catch {
      /* ignore — page still usable via regenerate/list */
    }
  }, [validRunId, setSearchParams]);

  const loadSummary = useCallback(async (runId: string) => {
    const generation = ++loadGenerationRef.current;
    setSummary(null);
    setLoading(true);
    setLoadState("idle");
    setErrorDetail(null);
    try {
      const data = await dailySummaryApi.getForRun(runId);
      if (generation !== loadGenerationRef.current) return;
      setSummary(data);
      localStorage.setItem(LAST_RUN_KEY, runId);
      setSearchParams({ run_id: runId }, { replace: true });
    } catch (err) {
      if (generation !== loadGenerationRef.current) return;
      setSummary(null);
      if (err instanceof ApiError && err.code === "SUMMARY_NOT_GENERATED") {
        setLoadState("no_summary");
      } else if (
        err instanceof ApiError &&
        (err.code === "NOT_FOUND" || err.status === 404)
      ) {
        setLoadState("run_not_found");
        setErrorDetail(err.message);
      } else {
        setLoadState("error");
        setErrorDetail(err instanceof Error ? err.message : "Could not load summary");
      }
    } finally {
      if (generation === loadGenerationRef.current) {
        setLoading(false);
      }
    }
  }, [setSearchParams]);

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    if (validRunId) {
      void loadSummary(validRunId);
    }
  }, [validRunId, loadSummary]);

  const onCopy = async () => {
    if (!summary?.text) return;
    setBusy("copy");
    try {
      await navigator.clipboard.writeText(summary.text);
      if (summary.run_id) {
        try {
          await dailySummaryApi.markCopied(summary.run_id);
        } catch {
          /* non-fatal */
        }
      }
      showToast("success", "Summary copied to clipboard");
    } catch {
      showToast("error", "Copy failed", "Could not copy summary text.");
    } finally {
      setBusy(null);
    }
  };

  const onDownload = async () => {
    if (!summary) return;
    setBusy("download");
    try {
      const name = summary.report_date
        ? `Rail_Madad_Daily_Summary_${summary.report_date}.txt`
        : undefined;
      await dailySummaryApi.downloadTxt(summary.summary_id, name);
      showToast("success", "Summary downloaded");
    } catch (err) {
      showToast("error", "Download failed", err instanceof Error ? err.message : undefined);
    } finally {
      setBusy(null);
    }
  };

  const onRegenerate = async () => {
    if (!validRunId) return;
    setBusy("regenerate");
    try {
      const data = await dailySummaryApi.regenerate(validRunId);
      setSummary(data);
      setLoadState("idle");
      setErrorDetail(null);
      showToast("success", "Summary regenerated");
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? `${err.message}${err.code ? ` (${err.code})` : ""}`
          : err instanceof Error
            ? err.message
            : "Regenerate failed";
      showToast("error", "Regenerate failed", detail);
    } finally {
      setBusy(null);
    }
  };

  const onShowPrevious = async () => {
    setShowPrevious(true);
    try {
      const res = await dailySummaryApi.list(30, 0);
      setPrevious(res.items);
    } catch (err) {
      showToast("error", "Could not load previous summaries", err instanceof Error ? err.message : undefined);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Daily Summary"
        description="Copy-ready WhatsApp-style briefing from the current run’s Previous-Day data (Reports 1–2, 3–7, 9, and 10–13)."
      />

      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <Card className="border-rail-line h-fit">
          <CardHeader>
            <CardTitle className="text-sm">Previous runs</CardTitle>
          </CardHeader>
          <CardBody className="max-h-[60vh] space-y-1 overflow-y-auto p-2">
            {runs.length === 0 ? (
              <p className="px-2 py-4 text-xs text-rail-muted">No runs yet.</p>
            ) : (
              runs.map((r) => (
                <button
                  key={r.run_id}
                  type="button"
                  onClick={() => {
                    setSearchParams({ run_id: r.run_id });
                    localStorage.setItem(LAST_RUN_KEY, r.run_id);
                  }}
                  className={cn(
                    "w-full rounded-lg px-3 py-2 text-left text-xs transition-colors",
                    selectedRunId === r.run_id
                      ? "bg-primary/10 text-primary"
                      : "hover:bg-surface text-rail-ink",
                  )}
                >
                  <div className="font-medium">{r.run_id.slice(0, 8)}…</div>
                  <div className="text-rail-muted">
                    {r.status}
                    {r.completed_at ? ` · ${formatDateTime12h(r.completed_at)}` : ""}
                  </div>
                </button>
              ))
            )}
          </CardBody>
        </Card>

        <div className="space-y-4">
          {loading ? <p className="text-sm text-rail-muted">Loading summary…</p> : null}
          {!loading && !summary && loadState !== "idle" ? (
            <Card>
              <CardBody className="space-y-3 py-8 text-center">
                <p className="text-sm text-rail-muted">
                  {loadState === "no_summary"
                    ? "No summary generated yet for this run."
                    : loadState === "run_not_found"
                      ? "Run not found. Select a completed run from the list."
                      : errorDetail ?? "Could not load summary."}
                </p>
                {validRunId && loadState !== "run_not_found" ? (
                  <Button
                    type="button"
                    onClick={() => void onRegenerate()}
                    disabled={busy === "regenerate" || runIsProcessing}
                  >
                    <RefreshCw className="mr-1 h-3.5 w-3.5" />
                    Generate / Regenerate
                  </Button>
                ) : (
                  <Button asChild>
                    <Link to="/automation">Go to Automation</Link>
                  </Button>
                )}
              </CardBody>
            </Card>
          ) : null}

          {summary ? (
            <>
              <Card className="border-rail-line">
                <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <FileText size={18} />
                      Report date {summary.report_date || "—"}
                    </CardTitle>
                    <CardDescription>
                      Summary: {summary.status}
                      {summary.run_status ? ` · Run: ${summary.run_status}` : ""}
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" size="sm" variant="secondary" disabled={!summary.text || busy === "copy"} onClick={() => void onCopy()}>
                      <ClipboardCopy className="mr-1 h-3.5 w-3.5" />
                      Copy Summary
                    </Button>
                    <Button type="button" size="sm" variant="secondary" disabled={busy === "download"} onClick={() => void onDownload()}>
                      <Download className="mr-1 h-3.5 w-3.5" />
                      Download TXT
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      disabled={busy === "regenerate" || runIsProcessing}
                      onClick={() => void onRegenerate()}
                    >
                      <RefreshCw className="mr-1 h-3.5 w-3.5" />
                      Regenerate
                    </Button>
                    <Button type="button" size="sm" variant="secondary" onClick={() => void onShowPrevious()}>
                      <History className="mr-1 h-3.5 w-3.5" />
                      View Previous
                    </Button>
                  </div>
                </CardHeader>
                <CardBody className="space-y-3">
                  <div className="text-xs text-rail-muted">
                    Sources:{" "}
                    {summary.source_reports.length
                      ? summary.source_reports.join(", ")
                      : "none"}
                  </div>
                  {summary.missing_reports.length > 0 ? (
                    <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      Missing / unavailable: {summary.missing_reports.join(", ")}
                    </p>
                  ) : null}
                  {summary.error_message ? (
                    <p className="text-xs text-red-600">{summary.error_message}</p>
                  ) : null}
                  <pre className="max-h-[55vh] overflow-auto whitespace-pre-wrap rounded-xl border border-rail-line bg-surface p-4 text-[13px] leading-relaxed text-rail-ink font-sans">
                    {summary.text || "(empty)"}
                  </pre>
                </CardBody>
              </Card>

              {showPrevious ? (
                <Card className="border-rail-line">
                  <CardHeader>
                    <CardTitle className="text-sm">Previous summaries</CardTitle>
                  </CardHeader>
                  <CardBody className="space-y-2">
                    {previous.length === 0 ? (
                      <p className="text-xs text-rail-muted">No previous summaries.</p>
                    ) : (
                      previous.map((item) => (
                        <button
                          key={item.summary_id}
                          type="button"
                          className="flex w-full items-center justify-between rounded-lg border border-rail-line px-3 py-2 text-left text-xs hover:bg-surface"
                          onClick={() => {
                            if (item.run_id) {
                              setSearchParams({ run_id: item.run_id });
                              localStorage.setItem(LAST_RUN_KEY, item.run_id);
                            }
                          }}
                        >
                          <span>
                            {item.report_date || "—"} · {item.status}
                          </span>
                          <span className="text-rail-muted">
                            {item.created_at ? formatDateTime12h(item.created_at) : ""}
                          </span>
                        </button>
                      ))
                    )}
                  </CardBody>
                </Card>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
