import {
  AlertCircle,
  CheckCircle2,
  Circle,
  Clock,
  Loader2,
  Minus,
  XCircle,
} from "lucide-react";
import { AnimatedProgressBar } from "@/features/automation/components/AnimatedProgressBar";
import type { AutomationStep, AutomationStepStatus } from "@/features/automation/types/automation";
import {
  computeRemainingMinutes,
  formatRemainingTime,
  getCurrentTask,
  getStepStats,
  statusLabel,
} from "@/features/automation/utils/display";
import { cn } from "@/utils/cn";

function StepIcon({ status }: { status: AutomationStepStatus }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-green-600" aria-hidden="true" />;
    case "partial":
      return <CheckCircle2 className="h-4 w-4 text-amber-500" aria-hidden="true" />;
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-600" aria-hidden="true" />;
    default:
      return <Circle className="h-4 w-4 text-slate-300" aria-hidden="true" />;
  }
}

function StatPill({
  label,
  count,
  variant,
}: {
  label: string;
  count: number;
  variant: "success" | "error" | "info" | "neutral";
}) {
  const styles = {
    success: "border-green-100 bg-green-50/80 text-green-800",
    error: "border-red-100 bg-red-50/80 text-red-800",
    info: "border-primary/20 bg-primary-muted text-primary",
    neutral: "border-slate-100 bg-slate-50 text-slate-600",
  };

  return (
    <div className={cn("rounded-lg border px-3 py-2 text-center text-xs", styles[variant])}>
      <p className="font-semibold tabular-nums">{count}</p>
      <p className="text-slate-500">{label}</p>
    </div>
  );
}

interface AutomationProgressPanelProps {
  steps: AutomationStep[];
  progressPercent: number;
  isBusy: boolean;
  isPaused: boolean;
  hasFailed: boolean;
  isComplete: boolean;
}

/** Display steps — hide internal login step label in timeline if desired */
function getDisplaySteps(steps: AutomationStep[]): AutomationStep[] {
  return steps.filter((s) => s.id !== "login");
}

export function AutomationProgressPanel({
  steps,
  progressPercent,
  isBusy,
  isPaused,
  hasFailed,
  isComplete,
}: AutomationProgressPanelProps) {
  const displaySteps = getDisplaySteps(steps);
  const stats = getStepStats(steps);
  const currentTask = getCurrentTask(steps);
  const remainingMinutes = computeRemainingMinutes(steps);

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Current report</p>
        {currentTask && currentTask.id !== "login" ? (
          <p className="mt-1 font-medium text-slate-900">{currentTask.label}</p>
        ) : currentTask?.id === "login" ? (
          <p className="mt-1 font-medium text-slate-900">Preparing reports…</p>
        ) : isComplete && !hasFailed ? (
          <p className="mt-1 font-medium text-green-700">All reports complete</p>
        ) : hasFailed ? (
          <p className="mt-1 font-medium text-red-700">Generation stopped — check activity log</p>
        ) : (
          <p className="mt-1 text-slate-600">Ready to generate</p>
        )}
      </div>

      {displaySteps.length > 0 && isBusy && (
        <div className="grid grid-cols-4 gap-2">
          <StatPill label="Done" count={stats.completed} variant="success" />
          <StatPill label="Failed" count={stats.failed} variant="error" />
          <StatPill label="Generating" count={stats.running} variant="info" />
          <StatPill label="Waiting" count={stats.waiting} variant="neutral" />
        </div>
      )}

      <div className="space-y-2">
        <AnimatedProgressBar
          value={progressPercent}
          label="Progress"
          isActive={isBusy && !isPaused}
        />
        {isBusy && (
          <p className="flex items-center gap-1.5 text-xs text-slate-500">
            <Clock className="h-3.5 w-3.5" />
            {formatRemainingTime(remainingMinutes)}
          </p>
        )}
      </div>

      <ul className="space-y-1" role="list">
        {displaySteps.map((step) => (
          <li
            key={step.id}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm",
              step.status === "running" && "bg-primary/5",
              step.status === "completed" && "text-slate-700",
              step.status === "failed" && "bg-red-50/50",
              step.status === "waiting" && "text-slate-400",
            )}
          >
            <StepIcon status={step.status} />
            <div className="min-w-0 flex-1">
              <span className="font-medium">{step.label}</span>
              {step.status === "failed" && step.error ? (
                <p className="mt-0.5 truncate text-xs text-red-700" title={step.error}>
                  {step.error}
                </p>
              ) : null}
            </div>
            <span className="text-xs">{statusLabel(step.status)}</span>
          </li>
        ))}
      </ul>

      {displaySteps.length === 0 && (
        <p className="text-sm text-slate-500">Select reports to see the generation timeline.</p>
      )}
    </div>
  );
}
