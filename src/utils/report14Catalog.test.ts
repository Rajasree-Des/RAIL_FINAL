import { describe, expect, it } from "vitest";
import { getReportDisplayName, REPORT_SLUG_ORDER, WORKFLOW_PATHS } from "@/utils/reportDisplayNames";
import { SCHEDULED_REPORTS } from "@/features/home/homeData";
import { AUTOMATION_REPORTS } from "@/features/automation/constants";

describe("Report 14 catalog registration", () => {
  it("is after comprehensive-10-13 and before report18 in slug order", () => {
    expect(REPORT_SLUG_ORDER).toHaveLength(11);
    expect(REPORT_SLUG_ORDER[7]).toBe("comprehensive-10-13");
    expect(REPORT_SLUG_ORDER[8]).toBe("report14");
    expect(REPORT_SLUG_ORDER[9]).toBe("report18");
    expect(REPORT_SLUG_ORDER[10]).toBe("bottom-report");
  });

  it("has display name and workflow path", () => {
    expect(getReportDisplayName("report14")).toBe("Report 14: Watering Complaints");
    const path = WORKFLOW_PATHS.find((w) => w.slug === "report14");
    expect(path?.path).toBe("/workflows/report14");
  });

  it("is on home scheduled reports before Report Vande Bharat", () => {
    expect(SCHEDULED_REPORTS).toHaveLength(11);
    expect(SCHEDULED_REPORTS[8].id).toBe("report14");
    expect(SCHEDULED_REPORTS[8].path).toBe("/workflows/report14");
  });

  it("is on automation reports before Report Vande Bharat", () => {
    expect(AUTOMATION_REPORTS).toHaveLength(11);
    expect(AUTOMATION_REPORTS[8].id).toBe("report14");
    expect(AUTOMATION_REPORTS[8].workflowPath).toBe("/workflows/report14");
  });
});

describe("Report Vande Bharat catalog registration", () => {
  it("is before bottom-report in slug order", () => {
    expect(REPORT_SLUG_ORDER[REPORT_SLUG_ORDER.length - 2]).toBe("report18");
    expect(REPORT_SLUG_ORDER[REPORT_SLUG_ORDER.length - 1]).toBe("bottom-report");
  });

  it("has display name and workflow path", () => {
    expect(getReportDisplayName("report18")).toBe("Report Vande Bharat");
    const path = WORKFLOW_PATHS.find((w) => w.slug === "report18");
    expect(path?.path).toBe("/workflows/report18");
  });

  it("is on home scheduled reports before bottom report", () => {
    expect(SCHEDULED_REPORTS[SCHEDULED_REPORTS.length - 2].id).toBe("report18");
    expect(SCHEDULED_REPORTS[SCHEDULED_REPORTS.length - 2].path).toBe("/workflows/report18");
    expect(SCHEDULED_REPORTS[SCHEDULED_REPORTS.length - 1].id).toBe("bottom-report");
  });

  it("is on automation reports before bottom report", () => {
    expect(AUTOMATION_REPORTS[AUTOMATION_REPORTS.length - 2].id).toBe("report18");
    expect(AUTOMATION_REPORTS[AUTOMATION_REPORTS.length - 2].workflowPath).toBe(
      "/workflows/report18",
    );
    expect(AUTOMATION_REPORTS[AUTOMATION_REPORTS.length - 1].id).toBe("bottom-report");
  });
});
