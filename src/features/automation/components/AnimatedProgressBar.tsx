import { cn } from "@/utils/cn";

interface AnimatedProgressBarProps {
  value: number;
  max?: number;
  label?: string;
  showPercentage?: boolean;
  isActive?: boolean;
  className?: string;
}

export function AnimatedProgressBar({
  value,
  max = 100,
  label,
  showPercentage = true,
  isActive = false,
  className,
}: AnimatedProgressBarProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div className={cn("w-full", className)}>
      {(label || showPercentage) && (
        <div className="mb-2 flex items-center justify-between text-xs">
          {label && <span className="font-medium text-slate-700">{label}</span>}
          {showPercentage && (
            <span className="tabular-nums font-semibold text-primary">
              {Math.round(percentage)}%
            </span>
          )}
        </div>
      )}
      <div className="relative h-2.5 overflow-hidden rounded-full bg-slate-200">
        <div
          className="relative h-full rounded-full bg-primary transition-[width] duration-700 ease-out"
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={max}
        >
          {isActive && (
            <div
              className="absolute inset-0 animate-progress-shimmer bg-white/20"
              aria-hidden="true"
            />
          )}
        </div>
      </div>
    </div>
  );
}
