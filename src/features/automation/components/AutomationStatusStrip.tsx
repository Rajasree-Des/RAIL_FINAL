import { cn } from "@/utils/cn";
import { StatusBadge } from "@/components/ui/StatusBadge";

export interface AutomationStatusStripProps {
  isVisible: boolean;
  isPaused: boolean;
  progressPercent: number;
}

export function AutomationStatusStrip({
  isVisible,
  isPaused,
  progressPercent,
}: AutomationStatusStripProps) {
  if (!isVisible) return null;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3 text-sm shadow-card",
        isPaused
          ? "border-amber-200 bg-amber-50 text-amber-900"
          : "border-rail-line bg-white text-slate-700",
      )}
      role="status"
      aria-live="polite"
    >
      <span className="font-medium">
        {isPaused ? "Generation paused" : "Generating reports"}
        <span className="ml-2 font-normal text-slate-500">{progressPercent}% complete</span>
      </span>
      <StatusBadge variant={isPaused ? "warning" : "info"}>
        {isPaused ? "Paused" : "In progress"}
      </StatusBadge>
    </div>
  );
}
