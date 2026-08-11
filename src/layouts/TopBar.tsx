import { Menu } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ProfileDropdown } from "@/components/ProfileDropdown";

function formatTodayDate(): string {
  return new Date().toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

interface TopBarProps {
  pageTitle?: string;
  showTitle?: boolean;
  onMenuClick?: () => void;
}

export function TopBar({ pageTitle, showTitle = true, onMenuClick }: TopBarProps) {
  return (
    <header className="sticky top-0 z-30 -mx-4 flex h-[60px] shrink-0 items-center gap-4 border-b border-rail-line/60 bg-surface/95 px-4 backdrop-blur-md lg:-mx-6 lg:px-6">
      <Button
        className="lg:hidden"
        variant="ghost"
        size="sm"
        aria-label="Open menu"
        onClick={onMenuClick}
      >
        <Menu size={18} />
      </Button>

      <div className="min-w-0 flex-1">
        {showTitle && pageTitle ? (
          <h1 className="truncate text-sm font-medium text-rail-muted">{pageTitle}</h1>
        ) : (
          <p className="hidden text-sm font-medium text-rail-ink sm:block">
            RailMadad Report Center
          </p>
        )}
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        <time
          className="hidden text-xs tabular-nums text-rail-muted md:block"
          dateTime={new Date().toISOString().split("T")[0]}
        >
          {formatTodayDate()}
        </time>

        <div className="hidden h-6 w-px bg-rail-line sm:block" />

        <ProfileDropdown />
      </div>
    </header>
  );
}

export function getTimeGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good Morning";
  if (hour < 17) return "Good Afternoon";
  return "Good Evening";
}
