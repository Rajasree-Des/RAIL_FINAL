import { getReportDisplayName } from "@/utils/reportDisplayNames";

export interface AutomationReport {
  id: string;
  label: string;
  workflowPath: string;
  estimatedMinutes: number;
}

const AUTOMATION_REPORT_DEFS: Array<{
  id: string;
  slug: string;
  workflowPath: string;
  estimatedMinutes: number;
}> = [
  { id: "zone", slug: "report1", workflowPath: "/workflows/merging", estimatedMinutes: 2 },
  { id: "division", slug: "division", workflowPath: "/workflows/division", estimatedMinutes: 2 },
  { id: "train", slug: "train-no", workflowPath: "/workflows/train-no", estimatedMinutes: 2 },
  { id: "cause", slug: "types", workflowPath: "/workflows/types", estimatedMinutes: 2 },
  { id: "scr-train", slug: "scr-train", workflowPath: "/workflows/scr-train", estimatedMinutes: 2 },
  {
    id: "scr-station",
    slug: "scr-station",
    workflowPath: "/workflows/scr-station",
    estimatedMinutes: 2,
  },
  { id: "report9", slug: "report9", workflowPath: "/workflows/report9", estimatedMinutes: 3 },
  {
    id: "comprehensive-10-13",
    slug: "comprehensive-10-13",
    workflowPath: "/workflows/comprehensive-10-13",
    estimatedMinutes: 4,
  },
  { id: "report14", slug: "report14", workflowPath: "/workflows/report14", estimatedMinutes: 3 },
  { id: "report18", slug: "report18", workflowPath: "/workflows/report18", estimatedMinutes: 2 },
  {
    id: "bottom-report",
    slug: "bottom-report",
    workflowPath: "/workflows/bottom-report",
    estimatedMinutes: 5,
  },
];

export const AUTOMATION_REPORTS: AutomationReport[] = AUTOMATION_REPORT_DEFS.map((item) => ({
  id: item.id,
  label: getReportDisplayName(item.slug),
  workflowPath: item.workflowPath,
  estimatedMinutes: item.estimatedMinutes,
}));

export const LOGIN_STEP = {
  id: "login",
  label: "Connecting to RailMadad",
} as const;

export const ESTIMATED_LOGIN_MINUTES = 1;

export function getEstimatedMinutes(reportIds: string[]): number {
  const reportMinutes = AUTOMATION_REPORTS.filter((r) => reportIds.includes(r.id)).reduce(
    (sum, r) => sum + r.estimatedMinutes,
    0,
  );
  return ESTIMATED_LOGIN_MINUTES + reportMinutes;
}

export function formatEstimatedTime(minutes: number): string {
  if (minutes < 60) {
    return `~${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `~${hours}h ${mins}m` : `~${hours}h`;
}
