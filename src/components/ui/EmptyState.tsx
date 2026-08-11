import { isValidElement, type ElementType, type ReactNode } from "react";
import { cn } from "@/utils/cn";

type EmptyStateProps = {
  icon?: ElementType<{ className?: string }> | ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
};

function renderIcon(icon: EmptyStateProps["icon"]) {
  if (!icon) return null;
  if (isValidElement(icon)) return icon;

  const IconComponent = icon as ElementType<{ className?: string }>;
  return <IconComponent className="h-6 w-6" />;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 text-center",
        className,
      )}
    >
      {icon && (
        <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-400">
          {renderIcon(icon)}
        </div>
      )}
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
