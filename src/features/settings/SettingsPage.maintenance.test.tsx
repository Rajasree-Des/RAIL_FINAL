import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { SettingsPage } from "./SettingsPage";

const mockExportLogs = vi.fn();
const mockClearCache = vi.fn();
const mockInfo = vi.fn();
const mockShowToast = vi.fn();

vi.mock("@/hooks/usePermissions", () => ({
  usePermissions: () => ({ canManageSettings: true }),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: { username: "admin", email: "admin@example.com", role: "admin" },
    clearSession: vi.fn(),
  }),
}));

vi.mock("@/components/ui/Toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

vi.mock("@/api/system", () => ({
  systemApi: {
    info: (...args: unknown[]) => mockInfo(...args),
    exportLogs: (...args: unknown[]) => mockExportLogs(...args),
    clearCache: (...args: unknown[]) => mockClearCache(...args),
  },
}));

vi.mock("@/features/settings/hooks/useAppSettings", () => ({
  useAppSettings: () => ({
    categories: [],
    loading: false,
    saving: false,
    error: null,
    hasChanges: false,
    getValue: vi.fn(),
    setValue: vi.fn(),
    save: vi.fn(),
    resetCategory: vi.fn(),
    exportSettings: vi.fn(),
    importSettings: vi.fn(),
    reload: vi.fn(),
  }),
}));

vi.mock("@/features/dashboard/hooks/useDashboardAnalytics", () => ({
  clearAnalyticsCache: vi.fn(),
}));

vi.mock("@/features/home/hooks/useDashboardSummary", () => ({
  clearDashboardCache: vi.fn(),
}));

function renderSettings() {
  return render(
    <BrowserRouter>
      <SettingsPage />
    </BrowserRouter>,
  );
}

describe("SettingsPage System maintenance", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => "blob:test");
    global.URL.revokeObjectURL = vi.fn();
    mockInfo.mockResolvedValue({
      app_version: "1.0.0",
      environment: "development",
      backend: { ok: true, detail: "Running" },
      database: { ok: true, detail: "Connected" },
      database_type: "SQLite",
      cdp: { ok: false, detail: "Not reachable" },
      automation_status: "idle",
      active_run_id: null,
      last_successful_run_at: null,
      last_failed_run_at: null,
      storage_usage_bytes: 1024,
    });
  });

  it("exports logs and shows success toast", async () => {
    mockExportLogs.mockResolvedValue({
      blob: new Blob(["%PDF"], { type: "application/pdf" }),
      filename: "RailMadad_Administrative_Logs_test.pdf",
    });

    renderSettings();
    fireEvent.click(screen.getByRole("button", { name: /system/i }));
    await waitFor(() => expect(mockInfo).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /export logs/i }));

    await waitFor(() => {
      expect(mockExportLogs).toHaveBeenCalled();
      expect(mockShowToast).toHaveBeenCalledWith("success", "Administrative logs exported");
    });
  });

  it("shows backend error when export fails", async () => {
    mockExportLogs.mockRejectedValue(new Error("Export unavailable"));

    renderSettings();
    fireEvent.click(screen.getByRole("button", { name: /system/i }));
    await waitFor(() => expect(mockInfo).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /export logs/i }));

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith("error", "Export unavailable");
    });
  });

  it("opens clear cache confirmation and clears on confirm", async () => {
    mockClearCache.mockResolvedValue({
      success: true,
      cleared: ["settings", "dashboard_analytics"],
      files_removed: 24,
      directories_removed: 2,
      bytes_freed: 19_300_000,
      skipped_locked: 0,
      partial: false,
    });

    renderSettings();
    fireEvent.click(screen.getByRole("button", { name: /system/i }));
    await waitFor(() => expect(mockInfo).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /^clear cache$/i }));
    expect(
      screen.getByText(
        "Generated reports, logs, settings and user data will not be deleted.",
      ),
    ).toBeInTheDocument();

    const confirmButtons = screen.getAllByRole("button", { name: /^clear cache$/i });
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(mockClearCache).toHaveBeenCalled();
      expect(mockShowToast).toHaveBeenCalledWith(
        "success",
        expect.stringContaining("Cache cleared — 24 files removed"),
      );
    });
  });

  it("does not clear cache when confirmation is cancelled", async () => {
    renderSettings();
    fireEvent.click(screen.getByRole("button", { name: /system/i }));
    await waitFor(() => expect(mockInfo).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /^clear cache$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));

    expect(mockClearCache).not.toHaveBeenCalled();
  });
});
