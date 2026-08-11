/** Report card display guards for success vs pending error. */

import { describe, expect, it } from "vitest";

/** Mirror GeneratedReportsPage display rules for unit testing. */
export function reportCardDisplay(report: {
  status: string;
  error?: string | null;
  pdf_download_url?: string | null;
  pdf_preview_url?: string | null;
  excel_download_url?: string | null;
}) {
  const displayError = report.status === "success" ? null : report.error || null;
  const hasCurrentPdfUrl = Boolean(
    report.pdf_preview_url || report.pdf_download_url,
  );
  const hasCurrentExcelUrl = Boolean(report.excel_download_url);
  const pdfReady = Boolean(report.pdf_download_url);
  const excelReady = Boolean(report.excel_download_url);
  return {
    displayError,
    showPreview: pdfReady && hasCurrentPdfUrl && Boolean(report.pdf_preview_url),
    showPdfDownload: pdfReady && hasCurrentPdfUrl && Boolean(report.pdf_download_url),
    showExcelDownload: excelReady && hasCurrentExcelUrl,
  };
}

describe("Generated report card success/pending guards", () => {
  it("success with leftover pending error shows no red pending text", () => {
    const view = reportCardDisplay({
      status: "success",
      error: "Extracted; ingest/process pending",
      pdf_download_url: "/api/v1/automation/artifacts/p/download",
      pdf_preview_url: "/api/v1/automation/artifacts/p/preview",
      excel_download_url: "/api/v1/automation/artifacts/e/download",
    });
    expect(view.displayError).toBeNull();
    expect(view.showPreview).toBe(true);
    expect(view.showPdfDownload).toBe(true);
    expect(view.showExcelDownload).toBe(true);
  });

  it("success without artifact URLs hides Preview/Download", () => {
    const view = reportCardDisplay({
      status: "success",
      error: null,
    });
    expect(view.displayError).toBeNull();
    expect(view.showPreview).toBe(false);
    expect(view.showPdfDownload).toBe(false);
    expect(view.showExcelDownload).toBe(false);
  });

  it("failed shows backend error and no download gating on success URLs", () => {
    const view = reportCardDisplay({
      status: "failed",
      error: "Ingestion failed",
    });
    expect(view.displayError).toBe("Ingestion failed");
    expect(view.showPreview).toBe(false);
  });
});

describe("automation mapping success with stale pending", () => {
  it("maps status=success even if error still says pending", () => {
    const events: Array<{ type: string }> = [];
    const report = {
      slug: "train-no",
      status: "success",
      error: "Extracted; ingest/process pending",
    };
    const pendingDeferred =
      report.status === "partial_success" &&
      typeof report.error === "string" &&
      report.error.toLowerCase().includes("ingest/process pending");
    if (!pendingDeferred && report.status === "success") {
      events.push({ type: "step_completed" });
    }
    expect(events).toEqual([{ type: "step_completed" }]);
  });
});
