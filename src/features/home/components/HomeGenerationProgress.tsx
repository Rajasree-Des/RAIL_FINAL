import { Link } from "react-router-dom";
import {
  CheckCircle2,
  Circle,
  Loader2,
  Pause,
  Play,
  Square,
  XCircle,
} from "lucide-react";
import { AnimatedProgressBar } from "@/features/automation/components/AnimatedProgressBar";
import type { AutomationStep, AutomationStepStatus } from "@/features/automation/types/automation";
import {
  computeRemainingMinutes,
  formatRemainingTime,
  statusLabel,
} from "@/features/automation/utils/display";
import { Button } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { cn } from "@/utils/cn";

function StepIcon({ status }: { status: AutomationStepStatus }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-hidden="true" />;
    case "partial":
      return <CheckCircle2 className="h-4 w-4 text-amber-500" aria-hidden="true" />;
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden="true" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-red-500" aria-hidden="true" />;
    default:
      return <Circle className="h-4 w-4 text-slate-200" aria-hidden="true" />;
  }
}

export interface HomeGenerationProgressProps {
  steps: AutomationStep[];
  progressPercent: number;
  isBusy: boolean;
  isPaused: boolean;
  hasFailed: boolean;
  isStopped?: boolean;
  isComplete: boolean;
  acting: boolean;
  failureMessage?: string;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
}

function getDisplaySteps(steps: AutomationStep[]): AutomationStep[] {
  return steps.filter((s) => s.id !== "login");
}

export function HomeGenerationProgress({
  steps,
  progressPercent,
  isBusy,
  isPaused,
  hasFailed,
  isStopped = false,
  isComplete,
  acting,
  failureMessage,
  onPause,
  onResume,
  onStop,
}: HomeGenerationProgressProps) {
  const displaySteps = getDisplaySteps(steps);
  const remainingMinutes = computeRemainingMinutes(steps);
  const currentStep = displaySteps.find((s) => s.status === "running");

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <StatusBadge variant={isComplete ? "success" : isStopped ? "error" : hasFailed ? "error" : "info"}>
            {isComplete
              ? hasFailed
                ? "Completed with errors"
                : "Complete"
              : isStopped
                ? "Stopped"
                : hasFailed
                  ? "Failed"
                  : isPaused
                    ? "Paused"
                    : "In progress"}
          </StatusBadge>
          <h2 className="mt-3 text-xl font-semibold tracking-tight text-slate-900">
            {isComplete
              ? hasFailed
                ? "Reports finished with errors"
                : "Today's reports are ready"
              : isStopped
                ? "Report generation stopped"
                : hasFailed
                  ? "Report generation failed"
                  : currentStep
                    ? `Generating ${currentStep.label}`
                    : "Preparing reports…"}
          </h2>
          {hasFailed && failureMessage && (
            <p className="mt-2 max-w-2xl text-sm text-red-600">{failureMessage}</p>
          )}
          {isBusy && !isPaused && (
            <p className="mt-1 text-sm text-slate-500">{formatRemainingTime(remainingMinutes)}</p>
          )}
        </div>
        {isBusy && (
          <div className="flex gap-2">
            {isPaused ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void onResume()}
                disabled={acting}
              >
                <Play className="mr-1.5 h-3.5 w-3.5" />
                Resume
              </Button>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void onPause()}
                disabled={acting}
              >
                <Pause className="mr-1.5 h-3.5 w-3.5" />
                Pause
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void onStop()}
              disabled={acting && !isBusy}
            >
              <Square className="mr-1.5 h-3.5 w-3.5" />
              Stop
            </Button>
          </div>
        )}
      </div>

      <Card className="hover:shadow-card">
        <CardBody className="space-y-8 p-6 lg:p-8">
          <AnimatedProgressBar
            value={progressPercent}
            label="Overall progress"
            isActive={isBusy && !isPaused}
          />

          <ul className="space-y-1" role="list">
            {displaySteps.map((step, index) => (
              <li
                key={step.id}
                className={cn(
                  "flex items-center gap-4 rounded-lg px-3 py-3 text-sm transition-colors duration-200",
                  step.status === "running" && "bg-primary/5",
                  step.status === "failed" && "bg-red-50/50",
                )}
              >
                <span className="flex h-6 w-6 shrink-0 items-center justify-center text-xs text-slate-400">
                  {step.status === "completed" || step.status === "partial" ? (
                    <StepIcon status={step.status} />
                  ) : (
                    <span className="tabular-nums">{index + 1}</span>
                  )}
                </span>
                <StepIcon status={step.status} />
                <span className="flex-1 font-medium leading-snug break-words text-slate-800">
                  {step.label}
                </span>
                <span
                  className={cn(
                    "text-xs",
                    step.status === "waiting" && "text-slate-400",
                    step.status === "running" && "text-primary",
                    step.status === "completed" && "text-emerald-600",
                    step.status === "partial" && "text-amber-600",
                    step.status === "failed" && "text-red-600",
                  )}
                >
                  {statusLabel(step.status)}
                </span>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>

      {isComplete && (
        <Card className="border-emerald-100 bg-emerald-50/30 hover:shadow-card">
          <CardBody className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-2 text-sm text-slate-700">
              <p className="flex items-center gap-2 font-medium text-slate-900">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                Reports generated
              </p>
              <p className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                Dashboard updated
              </p>
              <p className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                Ready to download
              </p>
            </div>
            <Button asChild>
              <Link to="/dashboard">View Dashboard</Link>
            </Button>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
