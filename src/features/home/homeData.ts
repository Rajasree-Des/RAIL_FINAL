import type { LucideIcon } from "lucide-react";
import {
  BarChart3,
  Building2,
  Clock,
  FileCheck,
  FolderOpen,
  Layers,
  MapPin,
  ScrollText,
  SlidersHorizontal,
  Timer,
  Train,
} from "lucide-react";
import { getReportDisplayName } from "@/utils/reportDisplayNames";

export interface ScheduledReport {
  /** Backend report catalog slug — cards are matched by slug, never position. */
  id: string;
  name: string;
  icon: LucideIcon;
  duration: string;
  status: "Ready" | "Scheduled" | "Generated";
  path: string;
}

function scheduledReport(
  id: string,
  icon: LucideIcon,
  duration: string,
  path: string,
): ScheduledReport {
  return {
    id,
    name: getReportDisplayName(id),
    icon,
    duration,
    status: "Ready",
    path,
  };
}

export const SCHEDULED_REPORTS: ScheduledReport[] = [
  scheduledReport("report1", MapPin, "~2 min", "/workflows/merging"),
  scheduledReport("division", Building2, "~2 min", "/workflows/division"),
  scheduledReport("train-no", Train, "~2 min", "/workflows/train-no"),
  scheduledReport("types", BarChart3, "~2 min", "/workflows/types"),
  scheduledReport("scr-train", Train, "~2 min", "/workflows/scr-train"),
  scheduledReport("scr-station", Building2, "~2 min", "/workflows/scr-station"),
  scheduledReport("report9", Layers, "~3 min", "/workflows/report9"),
  scheduledReport("comprehensive-10-13", Layers, "~4 min", "/workflows/comprehensive-10-13"),
  scheduledReport("report14", Layers, "~3 min", "/workflows/report14"),
  scheduledReport("report18", Train, "~2 min", "/workflows/report18"),
  scheduledReport("bottom-report", Train, "~5 min", "/workflows/bottom-report"),
];

/** Icons for the live status metric cards (values come from /dashboard/summary). */
export const METRIC_ICONS = {
  lastGenerated: Clock,
  reportsAvailable: FileCheck,
  expectedTime: Timer,
  currentStatus: Layers,
} as const;

export const GENERATION_PIPELINE = [
  { step: 1, label: "Collect Report Data" },
  { step: 2, label: "Generate Reports" },
  { step: 3, label: "Update Dashboard" },
  { step: 4, label: "Generate PDFs" },
  { step: 5, label: "Ready for Download" },
];

export const QUICK_ACTIONS = [
  {
    label: "View Dashboard",
    description: "Analytics and complaint insights",
    icon: BarChart3,
    path: "/dashboard",
    permission: null,
  },
  {
    label: "Generated Reports",
    description: "Browse and download files",
    icon: FolderOpen,
    path: "/reports",
    permission: "reports" as const,
  },
  {
    label: "Report Configuration",
    description: "Filters and export settings",
    icon: SlidersHorizontal,
    path: "/workflows/merging",
    permission: null,
  },
  {
    label: "Activity Log",
    description: "Generation history and events",
    icon: ScrollText,
    path: "/logs",
    permission: "logs" as const,
  },
];
