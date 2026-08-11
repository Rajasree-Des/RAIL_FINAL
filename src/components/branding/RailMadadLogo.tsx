import { useDisplayPrefs } from "@/hooks/useDisplayPrefs";
import { cn } from "@/utils/cn";

const SIZES = {
  xs: "h-6",
  sm: "h-8",
  md: "h-10",
  lg: "h-14",
  xl: "h-16",
} as const;

export interface RailMadadLogoProps {
  className?: string;
  size?: keyof typeof SIZES;
  showWordmark?: boolean;
}

export function RailMadadLogo({ className, size = "md", showWordmark = false }: RailMadadLogoProps) {
  const { organizationName } = useDisplayPrefs();
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <img
        src="/images/railmadad-logo.gif"
        alt="RailMadad"
        className={cn("w-auto shrink-0 object-contain", SIZES[size])}
      />
      {showWordmark && (
        <div className="min-w-0">
        <p className="truncate text-sm font-semibold tracking-tight text-slate-900">RailMadad Report Center</p>
        <p className="truncate text-xs text-slate-400">{organizationName}</p>
        </div>
      )}
    </div>
  );
}
