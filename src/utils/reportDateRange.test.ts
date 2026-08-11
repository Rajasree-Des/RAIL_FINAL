import { describe, expect, it } from "vitest";
import {
  defaultReportDateFrom,
  defaultReportDateTo,
  formatReportDateLabel,
  validateReportDateRange,
} from "./reportDateRange";

describe("reportDateRange", () => {
  it("validates required range order", () => {
    expect(validateReportDateRange("2026-07-25", "2026-07-26")).toBeNull();
    expect(validateReportDateRange("", "2026-07-26")).toMatch(/required/i);
    expect(validateReportDateRange("2026-07-27", "2026-07-26")).toMatch(/not be after/i);
  });

  it("formats labels for preview copy", () => {
    expect(formatReportDateLabel("2026-07-25", "2026-07-26")).toBe(
      "25-07-2026 to 26-07-2026",
    );
  });

  it("defaults to consecutive IST calendar days", () => {
    expect(defaultReportDateFrom() <= defaultReportDateTo()).toBe(true);
  });
});
