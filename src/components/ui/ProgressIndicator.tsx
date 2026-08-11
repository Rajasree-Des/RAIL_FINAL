import { cn } from "@/utils/cn";

interface ProgressIndicatorProps {
  value: number;
  max?: number;
  label?: string;
  showPercentage?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function ProgressIndicator({
  value,
  max = 100,
  label,
  showPercentage = true,
  size = "md",
  className,
}: ProgressIndicatorProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  const sizeStyles = {
    sm: "h-1",
    md: "h-2",
    lg: "h-3",
  };

  return (
    <div className={cn("w-full", className)}>
      {(label || showPercentage) && (
        <div className="mb-1 flex items-center justify-between text-xs">
          {label && <span className="font-medium text-slate-700">{label}</span>}
          {showPercentage && (
            <span className="text-slate-500">{Math.round(percentage)}%</span>
          )}
        </div>
      )}
      <div className={cn("overflow-hidden rounded-full bg-slate-200", sizeStyles[size])}>
        <div
          className="h-full bg-primary transition-all duration-300"
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={max}
        />
      </div>
    </div>
  );
}
