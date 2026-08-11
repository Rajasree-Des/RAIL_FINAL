import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Pause,
  Play,
  RefreshCw,
  Square,
  Zap,
} from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAutomationDashboard } from "@/features/admin/automation/hooks/useAutomationDashboard";
import { cn } from "@/utils/cn";

function statusVariant(status: string): "success" | "error" | "warning" | "info" | "neutral" {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
      return "error";
    case "running":
      return "info";
    case "paused":
      return "warning";
    case "stopped":
      return "neutral";
    default:
      return "neutral";
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export function AutomationDashboardPage() {
  const {
    status,
    history,
    logs,
    loading,
    acting,
    isActive,
    isRunning,
    isPaused,
    runNow,
    stop,
    pause,
    resume,
    refresh,
  } = useAutomationDashboard();

  if (loading && !status) {
    return (
      <div className="flex justify-center py-24">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader
          title="Report Generation"
          description="Manage and monitor daily RailMadad report generation"
          breadcrumbs={[{ label: "Admin" }, { label: "Report Generation" }]}
        />
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => void refresh()} disabled={acting}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          {!isActive ? (
            <Button onClick={() => void runNow()} disabled={acting}>
              <Play className="mr-2 h-4 w-4" />
              Run Now
            </Button>
          ) : (
            <>
              {isRunning && (
                <Button variant="secondary" onClick={() => void pause()} disabled={acting}>
                  <Pause className="mr-2 h-4 w-4" />
                  Pause
                </Button>
              )}
              {isPaused && (
                <Button onClick={() => void resume()} disabled={acting}>
                  <Play className="mr-2 h-4 w-4" />
                  Resume
                </Button>
              )}
              <Button variant="secondary" onClick={() => void stop()} disabled={acting}>
                <Square className="mr-2 h-4 w-4" />
                Stop
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardBody className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/5 text-primary">
                <Zap className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Status</p>
                <p className="text-lg font-semibold text-slate-900">
                  {status?.active_run?.status ?? "Idle"}
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50 text-green-600">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Success Rate</p>
                <p className="text-lg font-semibold text-slate-900">
                  {status?.success_rate ?? 0}%
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                <Clock className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Last Run</p>
                <p className="text-sm font-semibold text-slate-900">
                  {formatTime(status?.last_run?.completed_at ?? status?.last_run?.started_at ?? null)}
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="pt-6">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-50 text-red-600">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-slate-500">Failures</p>
                <p className="text-lg font-semibold text-slate-900">
                  {status?.total_failures ?? 0}
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      {status?.active_run && (
        <Card>
          <CardHeader>
            <CardTitle>Active Run</CardTitle>
            <CardDescription>
              {status.active_run.profile_name} — {status.active_run.id.slice(0, 8)}…
            </CardDescription>
          </CardHeader>
          <CardBody>
            <div className="flex flex-wrap gap-6 text-sm">
              <div>
                <span className="text-slate-500">Started </span>
                <span className="font-medium">{formatTime(status.active_run.started_at)}</span>
              </div>
              <div>
                <span className="text-slate-500">Success </span>
                <span className="font-medium">{status.active_run.success_count}</span>
              </div>
              <div>
                <span className="text-slate-500">Failed </span>
                <span className="font-medium">{status.active_run.failure_count}</span>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Run History</CardTitle>
            <CardDescription>Recent report generation runs</CardDescription>
          </CardHeader>
          <CardBody>
            {history.length === 0 ? (
              <p className="text-sm text-slate-500">No runs yet.</p>
            ) : (
              <div className="space-y-3">
                {history.map((run) => (
                  <div
                    key={run.id}
                    className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-3"
                  >
                    <div>
                      <p className="font-medium text-slate-900">{run.profile_name}</p>
                      <p className="text-xs text-slate-500">{formatTime(run.created_at)}</p>
                    </div>
                    <StatusBadge variant={statusVariant(run.status)}>
                      {run.status}
                    </StatusBadge>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Logs</CardTitle>
            <CardDescription>Live report generation output</CardDescription>
          </CardHeader>
          <CardBody>
            <div className="max-h-80 overflow-y-auto rounded-lg bg-slate-950 p-4 font-mono text-xs">
              {logs.length === 0 ? (
                <p className="text-slate-500">No logs available.</p>
              ) : (
                logs.map((log) => (
                  <div
                    key={log.id}
                    className={cn(
                      "mb-1",
                      log.level === "error" && "text-red-400",
                      log.level === "warning" && "text-amber-400",
                      log.level === "info" && "text-slate-300",
                    )}
                  >
                    <span className="text-slate-500">{log.created_at.slice(11, 19)}</span>{" "}
                    [{log.level.toUpperCase()}] {log.message}
                  </div>
                ))
              )}
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
