import { useMemo, useState, type ReactNode } from "react";
import { Download, Eye, FileSpreadsheet, Inbox } from "lucide-react";
import { automationApi } from "@/api/automation";
import type {
  DashboardAnalytics,
  DashboardStatus,
  DashboardSummary,
  NameCount,
  ReportCardInfo,
} from "@/api/dashboard";
import { PageHeader } from "@/components/PageHeader";
import { PdfPreviewModal } from "@/components/PdfPreviewModal";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import {
  currentStatusDisplay,
  reportStatusLabel,
} from "@/features/home/dashboardDisplay";
import { useDashboardSummary } from "@/features/home/hooks/useDashboardSummary";
import { useDashboardAnalytics } from "@/features/dashboard/hooks/useDashboardAnalytics";
import { usePermissions } from "@/hooks/usePermissions";
import { formatDateTime12h } from "@/utils/datetime";
import { getReportDisplayName, getReportDownloadName } from "@/utils/reportDisplayNames";
import { cn } from "@/utils/cn";

const TERMINAL_STATUSES: DashboardStatus[] = [
  "success",
  "partial_success",
  "failed",
  "skipped",
  "stopped",
];

function statusBadgeVariant(
  status: DashboardStatus,
): "success" | "error" | "warning" | "info" | "neutral" {
  switch (status) {
    case "success":
      return "success";
    case "failed":
      return "error";
    case "partial_success":
      return "warning";
    case "running":
    case "processing":
      return "info";
    default:
      return "neutral";
  }
}

function formatBytes(bytes: number | null): string {
  if (bytes == null || bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(seconds: number | null): string {
  if (seconds == null || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes}m ${rest}s`;
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function KpiCard({
  title,
  value,
  subtitle,
}: {
  title: string;
  value: string;
  subtitle?: string;
}) {
  return (
    <Card className="hover:shadow-card">
      <CardBody className="p-5">
        <p className="text-xs font-medium text-slate-500">{title}</p>
        <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums text-slate-900">
          {value}
        </p>
        {subtitle && <p className="mt-1 text-xs text-slate-400">{subtitle}</p>}
      </CardBody>
    </Card>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <Card className="hover:shadow-card">
      <CardHeader className="pb-1">
        <CardTitle className="text-base font-semibold text-slate-900">{title}</CardTitle>
        {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
      </CardHeader>
      <CardBody className="pt-3">{children}</CardBody>
    </Card>
  );
}

/** Horizontal bars scaled to the dataset's own maximum (never a fixed constant). */
function BarList({ items, unit }: { items: NameCount[]; unit?: string }) {
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <div className="space-y-3.5">
      {items.map((item) => (
        <div key={item.name}>
          <div className="mb-1 flex justify-between gap-3 text-sm">
            <span className="truncate text-slate-600" title={item.name}>
              {item.name}
            </span>
            <span className="shrink-0 font-medium tabular-nums text-slate-900">
              {item.count.toLocaleString("en-IN")}
              {unit ? ` ${unit}` : ""}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${(item.count / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function DataTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: (string | number)[][];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-rail-line text-left text-xs uppercase tracking-wide text-slate-400">
            {headers.map((h) => (
              <th key={h} className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-rail-line">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-surface">
              {row.map((cell, j) => (
                <td
                  key={j}
                  className={cn(
                    "px-3 py-2",
                    j === 0 ? "text-slate-400" : "text-slate-700",
                    typeof cell === "number" && "tabular-nums",
                  )}
                >
                  {typeof cell === "number" ? cell.toLocaleString("en-IN") : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WorkflowStatusCard({ summary }: { summary: DashboardSummary }) {
  const display = currentStatusDisplay(summary.current_status);
  const total = summary.total_enabled_reports;
  const completed = summary.reports.filter((r) =>
    TERMINAL_STATUSES.includes(r.status),
  ).length;
  const isActive =
    summary.current_status === "running" ||
    summary.current_status === "processing" ||
    summary.current_status === "paused";
  const current = isActive
    ? summary.reports.find(
        (r) => r.status === "running" || r.status === "processing",
      ) ?? summary.reports.find((r) => r.status === "pending")
    : undefined;
  const remaining = Math.max(0, total - completed);
  const progress = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <Section title="Workflow Status" subtitle={display.description}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
          <span className="flex items-center gap-2">
            <StatusBadge variant={statusBadgeVariant(summary.current_status)}>
              {display.label}
            </StatusBadge>
          </span>
          <span className="text-slate-600">
            Reports completed:{" "}
            <span className="font-medium tabular-nums text-slate-900">
              {completed}/{total}
            </span>
          </span>
          {isActive && current && (
            <span className="text-slate-600">
              Current report:{" "}
              <span className="font-medium text-slate-900">
                {getReportDisplayName(current.slug)}
              </span>
            </span>
          )}
          <span className="text-slate-600">
            Remaining:{" "}
            <span className="font-medium tabular-nums text-slate-900">{remaining}</span>
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              summary.current_status === "failed" ? "bg-red-500" : "bg-primary",
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </Section>
  );
}

function ReportCards({
  cards,
  isAdmin,
  onPreview,
  onDownload,
  busy,
}: {
  cards: ReportCardInfo[];
  isAdmin: boolean;
  onPreview: (url: string, title: string) => void;
  onDownload: (url: string, filename: string, key: string) => void;
  busy: string | null;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {cards.map((card) => {
        const pdf = card.files.find((f) => f.file_type === "pdf");
        const excel = card.files.find((f) => f.file_type === "excel");
        const displayName = getReportDisplayName(card.slug);
        return (
          <Card key={card.slug} className="border-rail-line">
            <CardHeader className="pb-1">
              <div className="flex items-start justify-between gap-2">
                <CardTitle className="text-sm leading-snug break-words pr-2">
                  {displayName}
                </CardTitle>
                <StatusBadge variant={statusBadgeVariant(card.status)}>
                  {reportStatusLabel(card.status)}
                </StatusBadge>
              </div>
            </CardHeader>
            <CardBody className="space-y-3 pt-2">
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-500">
                <dt>Generated</dt>
                <dd className="text-right tabular-nums text-slate-700">
                  {card.generated_at ? formatDateTime12h(card.generated_at) : "—"}
                </dd>
                <dt>Duration</dt>
                <dd className="text-right tabular-nums text-slate-700">
                  {formatDuration(card.duration_seconds)}
                </dd>
                <dt>PDF size</dt>
                <dd className="text-right tabular-nums text-slate-700">
                  {formatBytes(pdf?.file_size_bytes ?? null)}
                </dd>
                <dt>Excel size</dt>
                <dd className="text-right tabular-nums text-slate-700">
                  {formatBytes(excel?.file_size_bytes ?? null)}
                </dd>
                {card.sections_total != null && (
                  <>
                    <dt>Sections</dt>
                    <dd className="text-right tabular-nums text-slate-700">
                      {card.sections_total}
                    </dd>
                  </>
                )}
                {card.sections_total == null && card.row_count != null && (
                  <>
                    <dt>Rows</dt>
                    <dd className="text-right tabular-nums text-slate-700">
                      {card.row_count}
                    </dd>
                  </>
                )}
              </dl>
              {isAdmin && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={!pdf?.preview_url}
                    onClick={() =>
                      pdf?.preview_url && onPreview(pdf.preview_url, displayName)
                    }
                  >
                    <Eye className="mr-1 h-3.5 w-3.5" />
                    Preview
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={!pdf?.download_url || busy === `pdf-${card.slug}`}
                    onClick={() =>
                      pdf?.download_url &&
                      onDownload(
                        pdf.download_url,
                        `${getReportDownloadName(card.slug)}.pdf`,
                        `pdf-${card.slug}`,
                      )
                    }
                  >
                    <Download className="mr-1 h-3.5 w-3.5" />
                    PDF
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={!excel?.download_url || busy === `xlsx-${card.slug}`}
                    onClick={() =>
                      excel?.download_url &&
                      onDownload(
                        excel.download_url,
                        `${getReportDownloadName(card.slug)}.xlsx`,
                        `xlsx-${card.slug}`,
                      )
                    }
                  >
                    <FileSpreadsheet className="mr-1 h-3.5 w-3.5" />
                    Excel
                  </Button>
                </div>
              )}
            </CardBody>
          </Card>
        );
      })}
    </div>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardBody className="flex flex-col items-center gap-3 py-16 text-center">
        <Inbox className="h-10 w-10 text-slate-300" />
        <p className="text-base font-medium text-slate-700">No reports generated yet.</p>
        <p className="text-sm text-slate-400">
          Analytics will appear here after the first successful workflow run.
        </p>
      </CardBody>
    </Card>
  );
}

function AnalyticsSections({ analytics }: { analytics: DashboardAnalytics }) {
  const {
    zones,
    divisions,
    trains,
    complaint_types,
    feedback_distribution,
    top_causes,
    complaints_by_report,
  } = analytics;

  const resolutionByZone = useMemo(
    () =>
      zones
        .filter((z) => z.resolution_pct != null)
        .map((z) => ({ name: z.zone, count: Math.round(z.resolution_pct ?? 0) })),
    [zones],
  );

  return (
    <>
      {(complaints_by_report.length > 0 || feedback_distribution) && (
        <section className="grid gap-6 lg:grid-cols-2">
          {complaints_by_report.length > 0 && (
            <Section
              title="Complaint Distribution by Report"
              subtitle="Complaints captured in each generated report"
            >
              <BarList items={complaints_by_report} />
            </Section>
          )}
          {feedback_distribution && (
            <Section
              title="Feedback Distribution"
              subtitle={`${feedback_distribution.total.toLocaleString("en-IN")} feedback entries across zones`}
            >
              <BarList
                items={[
                  { name: "Excellent", count: feedback_distribution.excellent },
                  { name: "Satisfactory", count: feedback_distribution.satisfactory },
                  { name: "Unsatisfactory", count: feedback_distribution.unsatisfactory },
                ]}
              />
            </Section>
          )}
        </section>
      )}

      {(complaint_types.length > 0 || top_causes.length > 0) && (
        <section className="grid gap-6 lg:grid-cols-2">
          {complaint_types.length > 0 && (
            <Section
              title="Complaint Type Distribution"
              subtitle="From Report 5: Cause Wise Analysis"
            >
              <DataTable
                headers={["Type", "Complaints", "Share"]}
                rows={complaint_types.map((t) => [
                  t.type_name,
                  t.complaints,
                  `${t.percentage.toFixed(1)}%`,
                ])}
              />
            </Section>
          )}
          {top_causes.length > 0 && (
            <Section title="Top 10 Complaint Causes" subtitle="By complaint volume">
              <BarList items={top_causes} />
            </Section>
          )}
        </section>
      )}

      {(divisions.length > 0 || trains.length > 0 || resolutionByZone.length > 0) && (
        <section className="grid gap-6 lg:grid-cols-3">
          {divisions.length > 0 && (
            <Section title="Top 10 Affected Divisions" subtitle="By complaint volume">
              <BarList
                items={divisions
                  .slice(0, 10)
                  .map((d) => ({ name: d.division, count: d.complaints }))}
              />
            </Section>
          )}
          {trains.length > 0 && (
            <Section title="Top 10 Affected Trains" subtitle="By complaint volume">
              <BarList
                items={trains
                  .slice(0, 10)
                  .map((t) => ({ name: `${t.train_no} ${t.train_name}`, count: t.complaints }))}
              />
            </Section>
          )}
          {resolutionByZone.length > 0 && (
            <Section title="Resolution % by Zone" subtitle="Disposal rate per zone">
              <BarList items={resolutionByZone.slice(0, 10)} unit="%" />
            </Section>
          )}
        </section>
      )}

    </>
  );
}

export function DashboardPage() {
  const { isAdmin } = usePermissions();
  const { summary } = useDashboardSummary();
  const { analytics, loading, error } = useDashboardAnalytics();
  const [previewApiUrl, setPreviewApiUrl] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState("PDF Preview");
  const [busy, setBusy] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const onDownload = async (url: string, filename: string, key: string) => {
    setBusy(key);
    setDownloadError(null);
    try {
      const { blob, filename: serverName } = await automationApi.downloadBlob(
        url,
        filename,
      );
      triggerBlobDownload(blob, serverName || filename);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setBusy(null);
    }
  };

  const totals = analytics?.totals ?? null;
  const hasData = analytics?.has_data === true;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        description="Operational insights computed from the generated RailMadad reports."
      />

      {error && <p className="text-sm text-red-600">{error}</p>}
      {downloadError && <p className="text-sm text-red-600">{downloadError}</p>}

      {summary && <WorkflowStatusCard summary={summary} />}

      {loading && !analytics && (
        <p className="text-sm text-rail-muted">Loading analytics…</p>
      )}

      {analytics && !hasData && <EmptyState />}

      {hasData && totals && summary && (
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <KpiCard
            title="Total Complaints Received"
            value={totals.complaints_received.toLocaleString("en-IN")}
            subtitle="Sum across all zones"
          />
          <KpiCard
            title="Total Feedback Received"
            value={totals.feedback_received.toLocaleString("en-IN")}
            subtitle="Sum across all zones"
          />
          <KpiCard
            title="Complaints Resolved"
            value={totals.complaints_resolved.toLocaleString("en-IN")}
            subtitle="Closed complaints"
          />
          <KpiCard
            title="Resolution Rate"
            value={`${totals.resolution_rate.toFixed(1)}%`}
            subtitle="Resolved / received"
          />
          <KpiCard
            title="Reports Generated"
            value={`${summary.successful_report_count}/${summary.total_enabled_reports}`}
            subtitle="Latest run"
          />
          <KpiCard
            title="Last Generation"
            value={
              analytics.generated_at
                ? formatDateTime12h(analytics.generated_at)
                : "Never"
            }
            subtitle="Latest completed run"
          />
        </section>
      )}

      {hasData && analytics && <AnalyticsSections analytics={analytics} />}

      {hasData && analytics && analytics.report_cards.length > 0 && (
        <Section
          title="Generated Reports"
          subtitle="Files produced by the latest completed run"
        >
          <ReportCards
            cards={analytics.report_cards}
            isAdmin={isAdmin}
            onPreview={(url, title) => {
              setPreviewTitle(title);
              setPreviewApiUrl(url);
            }}
            onDownload={(url, filename, key) => void onDownload(url, filename, key)}
            busy={busy}
          />
        </Section>
      )}

      <PdfPreviewModal
        apiUrl={previewApiUrl}
        onClose={() => {
          setPreviewApiUrl(null);
          setPreviewTitle("PDF Preview");
        }}
        title={previewTitle}
      />
    </div>
  );
}
