import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/utils/cn";

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label?: ReactNode;
};

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, id, disabled, ...props }, ref) => {
    return (
      <label
        htmlFor={id}
        className={cn(
          "flex cursor-pointer items-center gap-3 rounded-md border border-slate-200 bg-white px-4 py-3",
          "hover:bg-slate-50",
          "focus-within:ring-2 focus-within:ring-primary focus-within:ring-offset-1",
          disabled && "cursor-not-allowed opacity-50 hover:bg-white",
          className,
        )}
      >
        <input
          ref={ref}
          type="checkbox"
          id={id}
          disabled={disabled}
          className={cn(
            "h-4 w-4 rounded border-slate-300 text-primary",
            "focus:ring-primary focus:ring-offset-0",
          )}
          {...props}
        />
        {label ? (
          <span className="flex flex-1 items-center justify-between text-sm font-medium text-slate-700">
            {label}
          </span>
        ) : null}
      </label>
    );
  },
);

Checkbox.displayName = "Checkbox";
