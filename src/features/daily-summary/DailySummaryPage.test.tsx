import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { DailySummaryPage } from "./DailySummaryPage";

const getForRun = vi.fn();
const listCdpRuns = vi.fn();

vi.mock("@/api/dailySummary", () => ({
  dailySummaryApi: {
    getForRun: (...args: unknown[]) => getForRun(...args),
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    regenerate: vi.fn(),
    markCopied: vi.fn(),
    downloadTxt: vi.fn(),
  },
}));

vi.mock("@/api/automation", () => ({
  automationApi: {
    listCdpRuns: (...args: unknown[]) => listCdpRuns(...args),
  },
}));

vi.mock("@/components/ui/Toast", () => ({
  useToast: () => ({ showToast: vi.fn() }),
}));

const RUN_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const RUN_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";

function renderPage(initialRunId = RUN_A) {
  return render(
    <MemoryRouter initialEntries={[`/daily-summary?run_id=${initialRunId}`]}>
      <Routes>
        <Route path="/daily-summary" element={<DailySummaryPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DailySummaryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listCdpRuns.mockResolvedValue([
      { run_id: RUN_A, status: "completed", completed_at: null },
      { run_id: RUN_B, status: "processing", completed_at: null },
    ]);
  });

  it("clears stale summary text while loading a different run", async () => {
    let resolveB: ((value: unknown) => void) | undefined;
    getForRun.mockImplementation((runId: string) => {
      if (runId === RUN_A) {
        return Promise.resolve({
          summary_id: "summary-a",
          run_id: RUN_A,
          report_date: "01.08.2026",
          status: "success",
          text: "Summary for RUN_A",
          source_reports: [],
          source_row_counts: {},
          missing_reports: [],
        });
      }
      return new Promise((resolve) => {
        resolveB = resolve;
      });
    });

    renderPage(RUN_A);
    await waitFor(() => {
      expect(screen.getByText("Summary for RUN_A")).toBeInTheDocument();
    });

    const runButtons = screen.getAllByRole("button");
    const runBButton = runButtons.find((btn) => btn.textContent?.includes("bbbbbbbb"));
    expect(runBButton).toBeTruthy();
    fireEvent.click(runBButton!);

    await waitFor(() => {
      expect(screen.queryByText("Summary for RUN_A")).not.toBeInTheDocument();
    });

    resolveB?.({
      summary_id: "summary-b",
      run_id: RUN_B,
      report_date: "01.08.2026",
      status: "success",
      text: "Summary for RUN_B",
      source_reports: [],
      source_row_counts: {},
      missing_reports: [],
    });

    await waitFor(() => {
      expect(screen.getByText("Summary for RUN_B")).toBeInTheDocument();
    });
  });

  it("disables regenerate while selected run is processing", async () => {
    getForRun.mockResolvedValue({
      summary_id: "summary-b",
      run_id: RUN_B,
      report_date: "01.08.2026",
      status: "success",
      text: "Summary for RUN_B",
      source_reports: [],
      source_row_counts: {},
      missing_reports: [],
      run_status: "processing",
    });

    renderPage(RUN_B);
    await waitFor(() => {
      expect(screen.getByText("Summary for RUN_B")).toBeInTheDocument();
    });

    const regenerateButtons = screen.getAllByRole("button", { name: /Regenerate/i });
    for (const button of regenerateButtons) {
      expect(button).toBeDisabled();
    }
  });
});
