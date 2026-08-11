import { describe, expect, it } from "vitest";
import {
  PAGE_ID_TO_SLUG,
  canDownloadExcel,
  canDownloadManualStatus,
  canDownloadPdf,
  canPreviewPdf,
  resolveReportSlug,
  usesDualManualArtifacts,
  type ManualRunStatus,
} from "@/api/reports";

const dualReadyBase: ManualRunStatus = {
  run_id: "run-1",
  report_slug: "report1",
  report_date: "15-07-2026",
  status: "Completed",
  run_status: "completed",
  source_row_count: 10,
  processed_row_count: 10,
  row_counts: {},
  extraction_success: true,
  ingestion_success: true,
  processing_success: true,
  artifact_id: "excel-1",
  preview_url: "/api/v1/automation/artifacts/pdf-1/preview",
  download_url: "/api/v1/automation/artifacts/excel-1/download",
  export_format: "xlsx",
  visible_columns: [],
  preview_rows: [],
  output_filename: "report.xlsx",
  output_file_size: 100,
  generated_at: null,
  error: null,
  excel_artifact_id: "excel-1",
  excel_download_url: "/api/v1/automation/artifacts/excel-1/download",
  excel_filename: "report.xlsx",
  excel_file_size: 100,
  pdf_artifact_id: "pdf-1",
  pdf_download_url: "/api/v1/automation/artifacts/pdf-1/download",
  pdf_preview_url: "/api/v1/automation/artifacts/pdf-1/preview",
  pdf_filename: "report.pdf",
  pdf_file_size: 200,
};

describe("report slug mapping", () => {
  it("maps all six configuration pages to canonical slugs", () => {
    expect(resolveReportSlug("merging")).toBe("report1");
    expect(resolveReportSlug("division")).toBe("division");
    expect(resolveReportSlug("train-no")).toBe("train-no");
    expect(resolveReportSlug("types")).toBe("types");
    expect(resolveReportSlug("scr-train")).toBe("scr-train");
    expect(resolveReportSlug("scr-station")).toBe("scr-station");
    expect(Object.keys(PAGE_ID_TO_SLUG)).toContain("merging");
  });

  it("uses canonical slugs in config and generate API paths", () => {
    const slug = resolveReportSlug("train-no");
    expect(slug).toBe("train-no");
    expect(`/reports/${encodeURIComponent(slug)}/config`).toBe("/reports/train-no/config");
    expect(`/reports/${encodeURIComponent(slug)}/generate`).toBe("/reports/train-no/generate");
    expect(`/reports/${encodeURIComponent(slug)}/preview`).toBe("/reports/train-no/preview");
  });

  it("maps legacy aliases to canonical slugs", () => {
    expect(resolveReportSlug("report2")).toBe("division");
    expect(resolveReportSlug("report3")).toBe("train-no");
    expect(resolveReportSlug("report4")).toBe("types");
    expect(resolveReportSlug("report5")).toBe("scr-train");
  });
});

describe("manual download gating", () => {
  it("requires current-run success flags and artifact", () => {
    const ready: ManualRunStatus = {
      run_id: "run-1",
      report_slug: "report5",
      report_date: "15-07-2026",
      status: "Completed",
      run_status: "completed",
      source_row_count: 10,
      processed_row_count: 10,
      row_counts: {},
      extraction_success: true,
      ingestion_success: true,
      processing_success: true,
      artifact_id: "art-1",
      preview_url: "/api/v1/automation/artifacts/art-1/preview",
      download_url: "/api/v1/automation/artifacts/art-1/download",
      export_format: "pdf",
      visible_columns: [],
      preview_rows: [],
      output_filename: "report.pdf",
      output_file_size: 100,
      generated_at: null,
      error: null,
    };
    expect(canDownloadManualStatus(ready)).toBe(true);

    const stale: ManualRunStatus = { ...ready, artifact_id: null, download_url: null };
    expect(canDownloadManualStatus(stale)).toBe(false);
  });

  it("dual report1 requires separate excel and pdf artifacts", () => {
    expect(usesDualManualArtifacts("report1")).toBe(true);
    expect(usesDualManualArtifacts("division")).toBe(true);
    expect(usesDualManualArtifacts("scr-train")).toBe(true);
    expect(usesDualManualArtifacts("scr-station")).toBe(true);
    expect(usesDualManualArtifacts("train-no")).toBe(true);
    expect(usesDualManualArtifacts("types")).toBe(true);
    expect(usesDualManualArtifacts("bottom-report")).toBe(true);
    expect(canDownloadExcel(dualReadyBase)).toBe(true);
    expect(canDownloadPdf(dualReadyBase)).toBe(true);
    expect(canPreviewPdf(dualReadyBase)).toBe(true);
    expect(canDownloadManualStatus(dualReadyBase)).toBe(true);

    const missingPdf = {
      ...dualReadyBase,
      pdf_artifact_id: null,
      pdf_download_url: null,
      pdf_preview_url: null,
    };
    expect(canDownloadPdf(missingPdf)).toBe(false);
    expect(canPreviewPdf(missingPdf)).toBe(false);
  });

  it("scr-train dual artifacts enable pdf preview and separate excel download", () => {
    const scrTrainReady: ManualRunStatus = {
      ...dualReadyBase,
      report_slug: "scr-train",
      excel_filename: "report5.xlsx",
      pdf_filename: "report5.pdf",
    };
    expect(canDownloadExcel(scrTrainReady)).toBe(true);
    expect(canDownloadPdf(scrTrainReady)).toBe(true);
    expect(canPreviewPdf(scrTrainReady)).toBe(true);
    expect(canDownloadManualStatus(scrTrainReady)).toBe(true);
  });
});
