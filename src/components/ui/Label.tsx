import { forwardRef, type LabelHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

type LabelProps = LabelHTMLAttributes<HTMLLabelElement> & {
  required?: boolean;
};

export const Label = forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, required, children, ...props }, ref) => {
    return (
      <label
        ref={ref}
        className={cn(
          "text-sm font-medium text-slate-700",
          className,
        )}
        {...props}
      >
        {children}
        {required ? (
          <span className="ml-1 text-red-500" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
    );
  },
);

Label.displayName = "Label";
