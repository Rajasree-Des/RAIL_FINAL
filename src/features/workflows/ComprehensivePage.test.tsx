import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { ComprehensivePage } from "./ComprehensivePage";
import { getReportDisplayName } from "@/utils/reportDisplayNames";

const { completedStatus } = vi.hoisted(() => ({
  completedStatus: {
    status: "Completed",
    pdf_preview_url: "/preview/test.pdf",
    excel_download_url: "/download/test.xlsx",
    preview_rows: [{ Division: "SC", Received: 10 }],
    visible_columns: ["Division", "Received"],
  },
}));

vi.mock("@/api/reports", () => ({
  reportsApi: {
    generate: vi.fn().mockResolvedValue({ run_id: "test-run-123" }),
    getRunStatus: vi.fn().mockResolvedValue(completedStatus),
    loadConfig: vi.fn().mockResolvedValue(null),
    saveConfig: vi.fn().mockResolvedValue(undefined),
    previewManualPdf: vi.fn().mockReturnValue("/preview/test.pdf"),
    downloadManualExcel: vi.fn(),
    downloadManualPdf: vi.fn(),
  },
  formatFileSize: vi.fn().mockReturnValue("1 KB"),
  canDownloadExcel: vi.fn().mockReturnValue(true),
  canDownloadPdf: vi.fn().mockReturnValue(true),
  canDownloadManualStatus: vi.fn().mockReturnValue(true),
  canPreviewPdf: vi.fn().mockReturnValue(true),
  isTerminalManualStatus: vi.fn().mockImplementation(
    (status: string) => status === "Completed" || status === "Failed",
  ),
}));

import { reportsApi } from "@/api/reports";

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe("ComprehensivePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(reportsApi.getRunStatus).mockResolvedValue(completedStatus as never);
  });

  describe("Page structure", () => {
    it("renders the page title", () => {
      renderWithRouter(<ComprehensivePage />);

      expect(
        screen.getByRole("heading", {
          level: 1,
          name: getReportDisplayName("comprehensive-10-13"),
        }),
      ).toBeInTheDocument();
    });

    it("renders report settings section", () => {
      renderWithRouter(<ComprehensivePage />);

      expect(screen.getByText("Report Settings")).toBeInTheDocument();
      expect(screen.getByLabelText("From Date")).toBeInTheDocument();
      expect(screen.getByLabelText("To Date")).toBeInTheDocument();
      expect(screen.getByLabelText("Export Format")).toBeInTheDocument();
    });

    it("renders portal filter summary with four sections", () => {
      renderWithRouter(<ComprehensivePage />);

      expect(screen.getByText("Portal filter summary")).toBeInTheDocument();
      expect(screen.getByText("Report 10 — C&W")).toBeInTheDocument();
      expect(screen.getByText("Report 11 — Security")).toBeInTheDocument();
      expect(screen.getByText("Report 12 — Punctuality")).toBeInTheDocument();
      expect(screen.getByText("Report 13 — Electrical Equipment")).toBeInTheDocument();
    });

    it("renders section column filters heading", () => {
      renderWithRouter(<ComprehensivePage />);

      expect(screen.getByText("Section Column Filters")).toBeInTheDocument();
    });

    it("renders generated output section", () => {
      renderWithRouter(<ComprehensivePage />);

      expect(screen.getByText("Generated Output")).toBeInTheDocument();
      expect(screen.queryByText("Report Preview")).not.toBeInTheDocument();
    });

    it("renders generate button", () => {
      renderWithRouter(<ComprehensivePage />);

      expect(
        screen.getByRole("button", { name: /Generate Report/i }),
      ).toBeInTheDocument();
    });

    it("renders save configuration button", () => {
      renderWithRouter(<ComprehensivePage />);

      expect(
        screen.getByRole("button", { name: /Save Configuration/i }),
      ).toBeInTheDocument();
    });
  });

  describe("Section cards", () => {
    it("renders all four section cards", () => {
      renderWithRouter(<ComprehensivePage />);

      expect(screen.getByText("Report 10 - C&W")).toBeInTheDocument();
      expect(screen.getByText("Report 11 - Security")).toBeInTheDocument();
      expect(screen.getByText("Report 12 - Punctuality")).toBeInTheDocument();
      expect(
        screen.getByText("Report 13 - Electrical Equipment"),
      ).toBeInTheDocument();
    });

    it("shows default column count for each section", () => {
      renderWithRouter(<ComprehensivePage />);

      const columnCounts = screen.getAllByText("11 columns selected");
      expect(columnCounts).toHaveLength(4);
    });

    it("expands section when clicked", () => {
      renderWithRouter(<ComprehensivePage />);

      const cwSection = screen.getByText("Report 10 - C&W");
      fireEvent.click(cwSection);

      expect(screen.getByText("Select All")).toBeInTheDocument();
      expect(screen.getByText("Clear All")).toBeInTheDocument();
      expect(screen.getByText("Reset Default")).toBeInTheDocument();
    });
  });

  describe("Column filters", () => {
    it("shows all 11 column options when section is expanded", () => {
      renderWithRouter(<ComprehensivePage />);

      const cwSection = screen.getByText("Report 10 - C&W");
      fireEvent.click(cwSection);

      expect(screen.getByText("S.No.")).toBeInTheDocument();
      expect(screen.getByText("Division")).toBeInTheDocument();
      expect(screen.getByText("Opening Balance")).toBeInTheDocument();
      expect(screen.getByText("Received")).toBeInTheDocument();
      expect(screen.getByText("% Share")).toBeInTheDocument();
      expect(screen.getByText("Closed")).toBeInTheDocument();
      expect(screen.getByText("Closing Balance")).toBeInTheDocument();
      expect(screen.getByText("% Disposal")).toBeInTheDocument();
      expect(screen.getByText("Avg. Disposal Time")).toBeInTheDocument();
      expect(screen.getByText("Avg. Rating")).toBeInTheDocument();
      expect(screen.getByText("Avg. Pendency Time")).toBeInTheDocument();
    });

    it("updates column count when column is deselected", async () => {
      renderWithRouter(<ComprehensivePage />);

      const cwSection = screen.getByText("Report 10 - C&W");
      fireEvent.click(cwSection);

      const checkbox = screen.getByRole("checkbox", { name: /Avg. Rating/i });
      fireEvent.click(checkbox);

      await waitFor(() => {
        expect(screen.getByText("10 columns selected")).toBeInTheDocument();
      });
    });

    it("Select All button selects all columns", async () => {
      renderWithRouter(<ComprehensivePage />);

      const cwSection = screen.getByText("Report 10 - C&W");
      fireEvent.click(cwSection);

      const checkbox = screen.getByRole("checkbox", { name: /Avg. Rating/i });
      fireEvent.click(checkbox);

      const selectAllBtn = screen.getByText("Select All");
      fireEvent.click(selectAllBtn);

      await waitFor(() => {
        const cwHeader = screen.getByText("Report 10 - C&W").closest("button");
        expect(cwHeader).toHaveTextContent("11 columns selected");
      });
    });

    it("Clear All clears all columns for the section", async () => {
      renderWithRouter(<ComprehensivePage />);

      const cwSection = screen.getByText("Report 10 - C&W");
      fireEvent.click(cwSection);

      const clearAllBtn = screen.getByText("Clear All");
      fireEvent.click(clearAllBtn);

      await waitFor(() => {
        expect(screen.getByText("0 columns selected")).toBeInTheDocument();
      });
    });
  });

  describe("Date range validation", () => {
    it("displays date range error when From Date is after To Date", async () => {
      renderWithRouter(<ComprehensivePage />);

      const fromInput = screen.getByLabelText("From Date");
      const toInput = screen.getByLabelText("To Date");

      fireEvent.change(fromInput, { target: { value: "2026-07-30" } });
      fireEvent.change(toInput, { target: { value: "2026-07-20" } });

      await waitFor(() => {
        expect(
          screen.getByText(/From Date must not be after To Date/i),
        ).toBeInTheDocument();
      });
    });

    it("disables Generate button when date range is invalid", async () => {
      renderWithRouter(<ComprehensivePage />);

      const fromInput = screen.getByLabelText("From Date");
      const toInput = screen.getByLabelText("To Date");

      fireEvent.change(fromInput, { target: { value: "2026-07-30" } });
      fireEvent.change(toInput, { target: { value: "2026-07-20" } });

      await waitFor(() => {
        const button = screen.getByRole("button", { name: /Generate Report/i });
        expect(button).toBeDisabled();
      });
    });
  });

  describe("Independent column filters", () => {
    it("changing Report 10 columns does not affect Report 11 columns", async () => {
      renderWithRouter(<ComprehensivePage />);

      const cwSection = screen.getByText("Report 10 - C&W");
      fireEvent.click(cwSection);

      const checkbox = screen.getByRole("checkbox", { name: /Avg. Rating/i });
      fireEvent.click(checkbox);

      fireEvent.click(cwSection);

      const securitySection = screen.getByText("Report 11 - Security");
      fireEvent.click(securitySection);

      await waitFor(() => {
        const checkboxes = screen.getAllByRole("checkbox", {
          name: /Avg. Rating/i,
        });
        expect(checkboxes[0]).toBeChecked();
      });
    });
  });

  describe("Generation payload", () => {
    it("sends per-section selected columns in the generate request", async () => {
      renderWithRouter(<ComprehensivePage />);

      const cwSection = screen.getByText("Report 10 - C&W");
      fireEvent.click(cwSection);

      fireEvent.click(screen.getByRole("checkbox", { name: /Opening Balance/i }));

      fireEvent.click(screen.getByRole("button", { name: /Generate Report/i }));

      await waitFor(() => {
        expect(reportsApi.generate).toHaveBeenCalled();
      });

      const payload = vi.mocked(reportsApi.generate).mock.calls[0]?.[1];
      expect(payload?.sections?.report10_cw.selected_column_ids).not.toContain(
        "opening_balance",
      );
      expect(payload?.sections?.report11_security.selected_column_ids).toContain(
        "opening_balance",
      );
      expect(payload?.date_from).toBeTruthy();
      expect(payload?.date_to).toBeTruthy();
      expect(payload?.configuration_source).toBe("manual_snapshot");
    });
  });

  describe("Save configuration", () => {
    it("calls saveConfig without generate", async () => {
      renderWithRouter(<ComprehensivePage />);

      fireEvent.click(screen.getByRole("button", { name: /Save Configuration/i }));

      await waitFor(() => {
        expect(reportsApi.saveConfig).toHaveBeenCalled();
      });
      expect(reportsApi.generate).not.toHaveBeenCalled();
    });
  });

  describe("Stale preview state", () => {
    it("shows regenerate banner after changing columns following a successful run", async () => {
      renderWithRouter(<ComprehensivePage />);

      fireEvent.click(screen.getByRole("button", { name: /Generate Report/i }));

      await waitFor(() => {
        expect(reportsApi.generate).toHaveBeenCalled();
      });

      await waitFor(
        () => {
          expect(screen.getByText("Completed")).toBeInTheDocument();
        },
        { timeout: 5000 },
      );

      const cwSection = screen.getByText("Report 10 - C&W");
      fireEvent.click(cwSection);
      fireEvent.click(screen.getByRole("checkbox", { name: /Avg. Rating/i }));

      await waitFor(() => {
        expect(
          screen.getByText(/Settings changed\. Generate again to update the preview\./i),
        ).toBeInTheDocument();
      });
    });
  });
});
