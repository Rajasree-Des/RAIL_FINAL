import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Settings,
  ScrollText,
  X,
  Home,
  ChevronDown,
  SlidersHorizontal,
  FolderOpen,
  FileText,
} from "lucide-react";
import { RailMadadLogo } from "@/components/branding/RailMadadLogo";
import { Button } from "@/components/ui/Button";
import { TopBar } from "@/layouts/TopBar";
import { cn } from "@/utils/cn";
import { usePermissions } from "@/hooks/usePermissions";
import { useNotificationRuntime } from "@/features/notifications/useNotificationRuntime";
import { getReportDisplayNameByPath, WORKFLOW_PATHS } from "@/utils/reportDisplayNames";

const SIDEBAR_W = 272;

const REPORT_CONFIG_ITEMS = WORKFLOW_PATHS.map(({ slug, path }) => ({
  id: slug,
  label: getReportDisplayNameByPath(path) ?? slug,
  path,
}));

const PAGE_TITLES: Record<string, string> = {
  "/home": "Operations Center",
  "/automation": "Generate Reports",
  "/dashboard": "Dashboard",
  "/reports": "Generated Reports",
  "/daily-summary": "Daily Summary",
  "/logs": "Activity Log",
  "/settings": "Settings",
  "/workflows/summary": "Summary Report",
  ...Object.fromEntries(
    WORKFLOW_PATHS.map(({ path }) => [path, getReportDisplayNameByPath(path) ?? path]),
  ),
};

function resolvePageTitle(pathname: string): string {
  if (PAGE_TITLES[pathname]) return PAGE_TITLES[pathname];
  if (pathname.startsWith("/admin/templates")) return "Templates";
  if (pathname.startsWith("/admin/prompts")) return "Prompts";
  if (pathname.startsWith("/workflows/")) return "Report Configuration";
  return "RailMadad Report Center";
}

function NavLinkItem({
  to,
  label,
  icon: Icon,
  onNavigate,
  indent = false,
}: {
  to: string;
  label: string;
  icon?: typeof Home;
  onNavigate?: () => void;
  indent?: boolean;
}) {
  return (
    <NavLink
      to={to}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "flex min-h-[38px] items-center gap-3 rounded-xl px-3 py-2 text-[13px] transition-all duration-200",
          indent && "pl-9",
          isActive
            ? "bg-primary/10 font-medium text-primary shadow-soft"
            : "text-rail-muted hover:bg-surface hover:text-rail-ink",
        )
      }
    >
      {Icon && (
        <Icon
          size={17}
          className="shrink-0 opacity-80"
          strokeWidth={1.75}
          aria-hidden="true"
        />
      )}
      <span
        className={cn(
          indent ? "leading-snug break-words line-clamp-2" : "truncate",
        )}
      >
        {label}
      </span>
    </NavLink>
  );
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { canManageSettings, canViewLogs, canViewReports } = usePermissions();
  const location = useLocation();
  const isReportConfigActive = location.pathname.startsWith("/workflows/");
  const [configOpen, setConfigOpen] = useState(isReportConfigActive);

  return (
    <nav aria-label="Main navigation" className="flex-1 overflow-y-auto px-3 py-2 scrollbar-thin">
      <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-rail-muted/80">
        Menu
      </p>
      <ul className="space-y-0.5" role="list">
        <li>
          <NavLinkItem to="/home" label="Home" icon={Home} onNavigate={onNavigate} />
        </li>
        <li>
          <NavLinkItem to="/dashboard" label="Dashboard" icon={LayoutDashboard} onNavigate={onNavigate} />
        </li>

        <li className="pt-3">
          <button
            type="button"
            onClick={() => setConfigOpen((o) => !o)}
            className={cn(
              "flex w-full min-h-[38px] items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium transition-all duration-200",
              isReportConfigActive
                ? "text-primary"
                : "text-rail-muted hover:bg-surface hover:text-rail-ink",
            )}
          >
            <SlidersHorizontal size={17} strokeWidth={1.75} className="shrink-0 opacity-80" />
            <span className="flex-1 truncate text-left">Report Configuration</span>
            <ChevronDown
              size={14}
              className={cn("opacity-50 transition-transform duration-200", configOpen && "rotate-180")}
            />
          </button>
          {configOpen && (
            <ul className="mt-1 space-y-0.5" role="list">
              {REPORT_CONFIG_ITEMS.map((item) => (
                <li key={item.id}>
                  <NavLinkItem to={item.path} label={item.label} onNavigate={onNavigate} indent />
                </li>
              ))}
            </ul>
          )}
        </li>

        {canViewReports && (
          <li className="pt-2">
            <NavLinkItem to="/reports" label="Generated Reports" icon={FolderOpen} onNavigate={onNavigate} />
          </li>
        )}
        {canViewReports && (
          <li>
            <NavLinkItem to="/daily-summary" label="Daily Summary" icon={FileText} onNavigate={onNavigate} />
          </li>
        )}
        {canViewLogs && (
          <li>
            <NavLinkItem to="/logs" label="Activity Log" icon={ScrollText} onNavigate={onNavigate} />
          </li>
        )}
        {canManageSettings && (
          <li>
            <NavLinkItem to="/settings" label="Settings" icon={Settings} onNavigate={onNavigate} />
          </li>
        )}
      </ul>
    </nav>
  );
}

function SidebarPanel({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <>
      <div className="shrink-0 border-b border-rail-line px-4 py-5">
        <RailMadadLogo size="sm" showWordmark />
      </div>
      <SidebarNav onNavigate={onNavigate} />
    </>
  );
}

export function AppShell() {
  useNotificationRuntime();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const isHome = location.pathname === "/home";
  const pageTitle = resolvePageTitle(location.pathname);

  return (
    <div className="min-h-screen bg-surface">
      {/* Floating desktop sidebar */}
      <div
        className="fixed bottom-4 left-4 top-4 z-30 hidden lg:block"
        style={{ width: SIDEBAR_W }}
      >
        <aside
          className="flex h-full flex-col overflow-hidden rounded-2xl border border-rail-line bg-white shadow-float"
          aria-label="Main navigation"
        >
          <SidebarPanel />
        </aside>
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div
            className="fixed inset-0 bg-rail-ink/20 backdrop-blur-sm"
            aria-hidden="true"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="fixed bottom-4 left-4 top-4 flex w-[min(280px,calc(100%-2rem))] flex-col overflow-hidden rounded-2xl border border-rail-line bg-white shadow-float">
            <div className="flex items-center justify-end border-b border-rail-line px-3 py-2">
              <Button variant="ghost" size="sm" aria-label="Close menu" onClick={() => setMobileOpen(false)}>
                <X size={18} />
              </Button>
            </div>
            <SidebarPanel onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-[calc(272px+2rem)]">
        <div className="mx-auto max-w-[1280px] px-4 pb-8 lg:px-6">
          <TopBar
            pageTitle={pageTitle}
            showTitle={!isHome}
            onMenuClick={() => setMobileOpen(true)}
          />

          <main className="animate-fade-in" id="main-content" tabIndex={-1}>
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
