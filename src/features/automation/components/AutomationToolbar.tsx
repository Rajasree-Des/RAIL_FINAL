import { Loader2, Pause, Play, RefreshCw, Square } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/Button";
import { cn } from "@/utils/cn";

export interface AutomationToolbarProps {
  acting: boolean;
  isActive: boolean;
  isRunning: boolean;
  isPaused: boolean;
  onRefresh: () => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
}

export function AutomationToolbar({
  acting,
  isActive,
  isRunning,
  isPaused,
  onRefresh,
  onPause,
  onResume,
  onStop,
}: AutomationToolbarProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <PageHeader
        title="Generate Today's Reports"
        description="All daily RailMadad reports will be generated. The dashboard and analytics update automatically when complete."
      />
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={onRefresh} disabled={acting}>
          <RefreshCw className={cn("mr-2 h-4 w-4", acting && "animate-spin")} />
          Refresh
        </Button>
        {isActive && (
          <>
            {isRunning && !isPaused && (
              <Button variant="secondary" onClick={onPause} disabled={acting}>
                <Pause className="mr-2 h-4 w-4" />
                Pause
              </Button>
            )}
            {isPaused && (
              <Button onClick={onResume} disabled={acting}>
                <Play className="mr-2 h-4 w-4" />
                Resume
              </Button>
            )}
            <Button variant="secondary" onClick={onStop} disabled={acting}>
              <Square className="mr-2 h-4 w-4" />
              Stop
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

export interface AutomationHeroProps {
  estimatedMinutesLabel: string;
  totalReports: number;
  isBusy: boolean;
  acting: boolean;
  canStart: boolean;
  onStart: () => void;
}

export function AutomationHero({
  estimatedMinutesLabel,
  totalReports,
  isBusy,
  acting,
  canStart,
  onStart,
}: AutomationHeroProps) {
  return (
    <div className="rounded-lg border border-rail-line bg-white p-6 shadow-card lg:p-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <p className="text-sm text-slate-500">
            {totalReports} reports · Estimated time {estimatedMinutesLabel}
          </p>
          <p className="max-w-lg text-sm text-slate-600">
            Select the reports you need below, then start generation. Progress appears in the
            timeline.
          </p>
        </div>
        <Button
          size="lg"
          className="h-12 min-w-[240px] px-8"
          onClick={onStart}
          disabled={acting || isBusy || !canStart}
        >
          {isBusy ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Generating…
            </>
          ) : (
            <>Generate Today&apos;s Reports</>
          )}
        </Button>
      </div>
    </div>
  );
}
