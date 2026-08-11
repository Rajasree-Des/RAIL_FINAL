/** Shared constants for Report 10–13 comprehensive configuration UI. */

export const AVAILABLE_COLUMNS = [
  { id: "sno", label: "S.No." },
  { id: "division", label: "Division" },
  { id: "opening_balance", label: "Opening Balance" },
  { id: "received", label: "Received" },
  { id: "share_percent", label: "% Share" },
  { id: "closed", label: "Closed" },
  { id: "closing_balance", label: "Closing Balance" },
  { id: "disposal_percent", label: "% Disposal" },
  { id: "avg_disposal_time", label: "Avg. Disposal Time" },
  { id: "avg_rating", label: "Avg. Rating" },
  { id: "avg_pendency_time", label: "Avg. Pendency Time" },
] as const;

export const DEFAULT_COLUMN_IDS = AVAILABLE_COLUMNS.map((c) => c.id);

export const COMPREHENSIVE_REPORT_ID = "comprehensive-10-13";

export const SECTION_COUNT = 4;

export const PORTAL_TAB = "Comprehensive";
export const PORTAL_ZONE = "South Central Railway";
export const PORTAL_VIEW = "Division Wise";

export interface ComprehensiveSectionDef {
  id: string;
  name: string;
  validationName: string;
  title: string;
  department: string;
  mode: string;
  complaintType: string;
}

export const SECTIONS: ComprehensiveSectionDef[] = [
  {
    id: "report10_cw",
    name: "Report 10 - C&W",
    validationName: "Report 10 — C&W",
    title: "C&W complaints division wise (as per comprehensive reports)",
    department: "Carriage & Wagon",
    mode: "Train",
    complaintType: "ALL",
  },
  {
    id: "report11_security",
    name: "Report 11 - Security",
    validationName: "Report 11 — Security",
    title: "Security complaints (as per comprehensive drop down)",
    department: "ALL",
    mode: "ALL",
    complaintType: "Security-Train",
  },
  {
    id: "report12_punctuality",
    name: "Report 12 - Punctuality",
    validationName: "Report 12 — Punctuality",
    title: "Punctuality complaints (as per comprehensive drop down)",
    department: "ALL",
    mode: "ALL",
    complaintType: "Punctuality-Train",
  },
  {
    id: "report13_electrical",
    name: "Report 13 - Electrical Equipment",
    validationName: "Report 13 — Electrical Equipment",
    title: "Electrical Equipment complaints division wise (as per comprehensive reports)",
    department: "ALL",
    mode: "ALL",
    complaintType: "Electrical Equipment-Train",
  },
];

export interface SectionColumnState {
  selectedColumns: string[];
  expanded: boolean;
}

export function buildDefaultSectionStates(): Record<string, SectionColumnState> {
  return Object.fromEntries(
    SECTIONS.map((s) => [s.id, { selectedColumns: [...DEFAULT_COLUMN_IDS], expanded: false }]),
  );
}

export function buildSectionsPayload(
  sectionStates: Record<string, SectionColumnState>,
): Record<string, { selected_column_ids: string[] }> {
  return Object.fromEntries(
    SECTIONS.map((section) => [
      section.id,
      { selected_column_ids: [...sectionStates[section.id].selectedColumns] },
    ]),
  );
}

export function validateSectionSelections(
  sectionStates: Record<string, SectionColumnState>,
): string | null {
  for (const section of SECTIONS) {
    if (sectionStates[section.id].selectedColumns.length < 1) {
      return `Select at least one column for ${section.validationName}.`;
    }
  }
  return null;
}

export function unionColumnIds(
  sectionStates: Record<string, SectionColumnState>,
): string[] {
  const seen = new Set<string>();
  const union: string[] = [];
  for (const section of SECTIONS) {
    for (const columnId of sectionStates[section.id].selectedColumns) {
      if (!seen.has(columnId)) {
        seen.add(columnId);
        union.push(columnId);
      }
    }
  }
  for (const columnId of DEFAULT_COLUMN_IDS) {
    if (seen.has(columnId) && !union.includes(columnId)) {
      union.push(columnId);
    }
  }
  return union;
}

export function buildConfigFingerprint(
  dateFrom: string,
  dateTo: string,
  exportFormat: string,
  sectionStates: Record<string, SectionColumnState>,
): string {
  const sections = buildSectionsPayload(sectionStates);
  return JSON.stringify({ dateFrom, dateTo, exportFormat, sections });
}
