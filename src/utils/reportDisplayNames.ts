/** Canonical report slugs → standardized UI display titles (frontend only). */

export const REPORT_DISPLAY_NAMES: Record<string, string> = {
  report1: "Report 1: Zone Wise Report",
  division: "Report 2: Division Report",
  "train-no": "Report 3: Top 20 Trains",
  types: "Report 5: Cause Wise Analysis",
  "scr-train": "Report 6: SCR Train Report",
  "scr-station": "Report 7: SCR Station Report",
  report9: "Report 9: All Zones Train/Station Cause Wise on Date",
  "comprehensive-10-13": "Report 10–13: Comprehensive Reports",
  report14: "Report 14: Watering Complaints",
  report18: "Report Vande Bharat",
  "bottom-report": "Bottom Performed Trains Report",
};

/** Preserved short names for client download fallbacks when server filename is absent. */
export const REPORT_DOWNLOAD_NAMES: Record<string, string> = {
  report1: "Zone Wise Report",
  division: "Division Report",
  "train-no": "Top 20 Trains",
  types: "Cause Wise Analysis",
  "scr-train": "SCR Train Report",
  "scr-station": "SCR Station Report",
  report9: "All Zones Train/Station Cause Wise on Date",
  "comprehensive-10-13": "Report 10-13 (Comprehensive Reports)",
  report14: "Watering Complaints",
  report18: "Report Vande Bharat",
  "bottom-report": "Bottom Performed Trains Report",
};

/** UI list order (Report 9 before Report 10–13 before Report 14 before Report Vande Bharat). */
export const REPORT_SLUG_ORDER = [
  "report1",
  "division",
  "train-no",
  "types",
  "scr-train",
  "scr-station",
  "report9",
  "comprehensive-10-13",
  "report14",
  "report18",
  "bottom-report",
] as const;

/** Automation progress UI ids → canonical slugs. */
export const AUTOMATION_ID_TO_SLUG: Record<string, string> = {
  zone: "report1",
  division: "division",
  train: "train-no",
  cause: "types",
  "scr-train": "scr-train",
  "scr-station": "scr-station",
  report9: "report9",
  "comprehensive-10-13": "comprehensive-10-13",
  report14: "report14",
  report18: "report18",
  "bottom-report": "bottom-report",
};

export function resolveReportSlug(slugOrId: string): string {
  return AUTOMATION_ID_TO_SLUG[slugOrId] ?? slugOrId;
}

export function getReportDisplayName(slug: string | null | undefined): string {
  if (!slug) return "Report";
  const resolved = resolveReportSlug(slug);
  return REPORT_DISPLAY_NAMES[resolved] ?? slug;
}

export function getReportDownloadName(slug: string | null | undefined): string {
  if (!slug) return "report";
  const resolved = resolveReportSlug(slug);
  return REPORT_DOWNLOAD_NAMES[resolved] ?? getReportDisplayName(resolved);
}

const SLUG_TO_WORKFLOW_PATH: Record<string, string> = {
  report1: "/workflows/merging",
  division: "/workflows/division",
  "train-no": "/workflows/train-no",
  types: "/workflows/types",
  "scr-train": "/workflows/scr-train",
  "scr-station": "/workflows/scr-station",
  report9: "/workflows/report9",
  "comprehensive-10-13": "/workflows/comprehensive-10-13",
  report14: "/workflows/report14",
  report18: "/workflows/report18",
  "bottom-report": "/workflows/bottom-report",
};

export const WORKFLOW_PATHS = REPORT_SLUG_ORDER.map((slug) => ({
  slug,
  path: SLUG_TO_WORKFLOW_PATH[slug],
})).filter((item) => item.path);

export function getReportDisplayNameByPath(path: string): string | undefined {
  const entry = WORKFLOW_PATHS.find((item) => item.path === path);
  return entry ? getReportDisplayName(entry.slug) : undefined;
}
