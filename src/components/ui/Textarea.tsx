import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  error?: boolean;
};

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          "flex min-h-24 w-full rounded-md border bg-white px-3 py-2 text-sm leading-relaxed",
          "placeholder:text-slate-400",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
          "disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-slate-50",
          "resize-none",
          error
            ? "border-red-500 focus-visible:ring-red-500"
            : "border-slate-200",
          className,
        )}
        {...props}
      />
    );
  },
);

Textarea.displayName = "Textarea";
