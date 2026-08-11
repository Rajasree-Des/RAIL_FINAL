import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/utils/cn";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "destructive";
  size?: "sm" | "md" | "lg";
  asChild?: boolean;
  children?: ReactNode;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "secondary", size = "md", asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";

    return (
      <Comp
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl font-medium",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
          "disabled:pointer-events-none disabled:opacity-50",
          "select-none transition-all duration-200",
          size === "sm" && "h-8 px-3 text-xs",
          size === "md" && "h-10 px-4 text-sm",
          size === "lg" && "h-12 px-6 text-base",
          variant === "primary" &&
            "bg-primary text-primary-foreground hover:bg-primary-hover active:bg-primary-hover",
          variant === "secondary" &&
            "border border-rail-line bg-white text-slate-900 hover:bg-slate-50 active:bg-slate-100",
          variant === "ghost" &&
            "text-slate-600 hover:bg-slate-100 hover:text-slate-900 active:bg-slate-200",
          variant === "destructive" &&
            "bg-red-600 text-white hover:bg-red-700 active:bg-red-800",
          className,
        )}
        {...props}
      />
    );
  },
);

Button.displayName = "Button";
