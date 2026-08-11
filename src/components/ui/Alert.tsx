import { forwardRef, type HTMLAttributes } from "react";
import { AlertCircle, CheckCircle2, Info, XCircle } from "lucide-react";
import { cn } from "@/utils/cn";

type AlertVariant = "info" | "success" | "warning" | "error";

type AlertProps = HTMLAttributes<HTMLDivElement> & {
  variant?: AlertVariant;
  title?: string;
};

const iconMap = {
  info: Info,
  success: CheckCircle2,
  warning: AlertCircle,
  error: XCircle,
};

const variantStyles = {
  info: "border-primary/20 bg-primary-muted text-primary",
  success: "border-green-200 bg-green-50 text-green-800",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  error: "border-red-200 bg-red-50 text-red-800",
};

export const Alert = forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = "info", title, children, ...props }, ref) => {
    const Icon = iconMap[variant];

    return (
      <div
        ref={ref}
        role="alert"
        className={cn(
          "flex gap-3 rounded-lg border p-4",
          variantStyles[variant],
          className,
        )}
        {...props}
      >
        <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
        <div className="flex-1">
          {title ? (
            <h4 className="mb-1 font-semibold">{title}</h4>
          ) : null}
          <div className="text-sm">{children}</div>
        </div>
      </div>
    );
  },
);

Alert.displayName = "Alert";
