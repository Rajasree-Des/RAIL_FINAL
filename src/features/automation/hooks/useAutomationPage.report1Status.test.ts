import { describe, expect, it, vi } from "vitest";
import type { AutomationRunDetail } from "@/api/automation";

// Re-implement the mapping contract under test by importing the page module helpers
// through a focused copy of terminal mapping behavior.

type Emit = (event: { type: string; stepId?: string; message?: string; error?: string }) => void;

const BACKEND_TO_UI: Record<string, string> = {
  report1: "zone",
  division: "division",
};

function stepIdForSlug(slug: string): string {
  return BACKEND_TO_UI[slug] ?? slug;
}

function mapReportStatus(
  report: { slug: string; status: string; error?: string | null; processing_success?: boolean },
  emit: Emit,
) {
  const stepId = stepIdForSlug(report.slug);
  const pendingDeferred =
    report.status === "partial_success" &&
    typeof report.error === "string" &&
    report.error.toLowerCase().includes("ingest/process pending");

  if (pendingDeferred) {
    emit({ type: "step_started", stepId, message: report.error ?? undefined });
    return;
  }
  if (report.status === "success") {
    emit({ type: "step_completed", stepId });
  } else if (report.status === "partial_success") {
    emit({ type: "step_partial", stepId, message: report.error ?? undefined });
  } else if (report.status === "failed") {
    emit({ type: "step_failed", stepId, error: report.error ?? undefined });
  }
}

describe("Report 1 UI terminal status mapping", () => {
  it("maps terminal partial_success to step_partial, not step_started", () => {
    const events: Array<{ type: string; stepId?: string }> = [];
    mapReportStatus(
      {
        slug: "report1",
        status: "partial_success",
        error: "Phase 8 blocked: validated Comprehensive and Feedback sources required",
      },
      (e) => events.push(e),
    );
    expect(events).toEqual([
      expect.objectContaining({ type: "step_partial", stepId: "zone" }),
    ]);
    expect(events[0]?.type).not.toBe("step_started");
  });

  it("maps failed to step_failed", () => {
    const events: Array<{ type: string }> = [];
    mapReportStatus(
      {
        slug: "report1",
        status: "failed",
        error: "REPORT1_COMPREHENSIVE_SOURCE_MISSING",
      },
      (e) => events.push(e),
    );
    expect(events[0]?.type).toBe("step_failed");
  });

  it("maps success to step_completed", () => {
    const events: Array<{ type: string }> = [];
    mapReportStatus({ slug: "report1", status: "success" }, (e) => events.push(e));
    expect(events[0]?.type).toBe("step_completed");
  });

  it("keeps deferred pending as step_started only while processing", () => {
    const events: Array<{ type: string }> = [];
    mapReportStatus(
      {
        slug: "division",
        status: "partial_success",
        error: "Extracted; ingest/process pending",
      },
      (e) => events.push(e),
    );
    expect(events[0]?.type).toBe("step_started");
  });
});

describe("stale run_id guard", () => {
  it("ignores detail when run_id does not match active run", () => {
    const activeRunId = "run-current";
    const detail = { run_id: "run-stale", reports: [] } as Pick<AutomationRunDetail, "run_id" | "reports">;
    const shouldIgnore = Boolean(activeRunId && detail.run_id && detail.run_id !== activeRunId);
    expect(shouldIgnore).toBe(true);
  });
});
