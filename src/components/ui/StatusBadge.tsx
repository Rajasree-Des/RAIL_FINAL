import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/utils/cn";

type StatusVariant = "neutral" | "info" | "success" | "warning" | "error";

interface StatusBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: StatusVariant;
  children: ReactNode;
}

const variantStyles: Record<StatusVariant, string> = {
  neutral: "bg-slate-100 text-slate-700 border-slate-200",
  info: "bg-primary-muted text-primary border-primary/20",
  success: "bg-green-50 text-green-700 border-green-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200",
  error: "bg-red-50 text-red-700 border-red-200",
};

export function StatusBadge({
  variant = "neutral",
  children,
  className,
  ...props
}: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        variantStyles[variant],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
