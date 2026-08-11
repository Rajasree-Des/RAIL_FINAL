/** Dashboard summary → Home card display mapping tests. */

import { describe, expect, it } from "vitest";
import type { DashboardSummary } from "@/api/dashboard";
import {
  currentStatusDisplay,
  formatExpectedTime,
  formatLastGenerated,
  generatedReportsValue,
  lastGeneratedDescription,
  reportStatusLabel,
  reportsAvailableDescription,
} from "./dashboardDisplay";
import { formatTime12h } from "@/utils/datetime";

function summary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    current_status: "ready",
    active_run_id: null,
    last_run_id: null,
    last_run_status: null,
    last_generated_at: null,
    successful_report_count: 0,
    failed_report_count: 0,
    generated_report_count: 0,
    total_enabled_reports: 7,
    estimated_duration_seconds: null,
    default_expected_duration_seconds: 900,
    reports: [],
    recent_activity: [],
    ...overrides,
  };
}

describe("current status card", () => {
  it("maps canonical statuses to labels", () => {
    expect(currentStatusDisplay("ready").label).toBe("Ready");
    expect(currentStatusDisplay("running").label).toBe("Running");
    expect(currentStatusDisplay("paused").label).toBe("Paused");
    expect(currentStatusDisplay("success").label).toBe("Completed");
    expect(currentStatusDisplay("partial_success").label).toBe("Partial Success");
    expect(currentStatusDisplay("failed").label).toBe("Failed");
    expect(currentStatusDisplay("stopped").label).toBe("Stopped");
  });

  it("terminal partial_success never displays as Generating", () => {
    expect(currentStatusDisplay("partial_success").label).not.toContain("Generating");
    expect(reportStatusLabel("partial_success")).toBe("Partial");
  });
});

describe("report status pill", () => {
  it("maps per-report canonical statuses", () => {
    expect(reportStatusLabel("success")).toBe("Generated");
    expect(reportStatusLabel("failed")).toBe("Failed");
    expect(reportStatusLabel("running")).toBe("Generating");
    expect(reportStatusLabel("pending")).toBe("Ready");
    expect(reportStatusLabel("stopped")).toBe("Stopped");
    expect(reportStatusLabel("skipped")).toBe("Skipped");
  });
});

describe("last generated card", () => {
  it("gates 'All N completed successfully' on a truly successful run", () => {
    const ok = summary({
      last_generated_at: new Date().toISOString(),
      last_run_status: "success",
      successful_report_count: 7,
    });
    expect(lastGeneratedDescription(ok)).toBe("All 7 reports completed successfully");
  });

  it("does not claim success for partial or failed runs", () => {
    const partial = summary({
      last_generated_at: new Date().toISOString(),
      last_run_status: "partial_success",
      successful_report_count: 4,
      failed_report_count: 2,
    });
    expect(lastGeneratedDescription(partial)).toBe("4 succeeded, 2 failed");
    expect(lastGeneratedDescription(partial)).not.toContain("completed successfully");

    const failed = summary({
      last_generated_at: new Date().toISOString(),
      last_run_status: "failed",
    });
    expect(lastGeneratedDescription(failed)).toBe("Last run failed");
  });

  it("shows Never when no runs exist", () => {
    expect(lastGeneratedDescription(summary())).toBe("No completed runs yet");
    expect(formatLastGenerated(null)).toBe("Never");
  });

  it("formats today's timestamps as local time", () => {
    const value = formatLastGenerated(new Date().toISOString());
    expect(value.startsWith("Today ")).toBe(true);
  });

  it("always uses IST 12-hour time with AM/PM, never 24-hour", () => {
    // 14:03 UTC = 19:33 IST
    const evening = new Date("2026-07-15T14:03:00Z");
    expect(formatTime12h(evening)).toBe("7:33 PM");

    const value = formatLastGenerated(evening.toISOString());
    expect(value).not.toContain("19:33");
    expect(value).toContain("7:33 PM");
  });
});

describe("expected time card", () => {
  it("falls back to the configured default when no history exists", () => {
    expect(formatExpectedTime(null, 900)).toBe("15 Minutes");
    expect(formatExpectedTime(null)).toBe("—");
  });

  it("formats seconds and minute ranges", () => {
    expect(formatExpectedTime(45)).toBe("~45 Seconds");
    expect(formatExpectedTime(150)).toBe("2–3 Minutes");
    expect(formatExpectedTime(120)).toBe("2 Minutes");
  });
});

describe("generated reports card", () => {
  it("renders X/Y from successful and total configured counts", () => {
    expect(
      generatedReportsValue(
        summary({ successful_report_count: 7, total_enabled_reports: 7 }),
      ),
    ).toBe("7/7");
    expect(generatedReportsValue(summary())).toBe("0/7");
  });

  it("describes generated artifact count", () => {
    expect(reportsAvailableDescription(summary({ generated_report_count: 12 }))).toBe(
      "12 files ready to preview and download",
    );
    expect(reportsAvailableDescription(summary())).toBe("Ready to generate");
  });
});
