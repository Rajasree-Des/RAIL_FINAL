import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  apiRequest: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(
      message: string,
      public status: number,
    ) {
      super(message);
      this.name = "ApiError";
    }
  },
}));

import { apiRequest } from "@/api/client";
import { automationApi } from "@/api/automation";
import {
  isTerminalRunStatus,
  isActiveRunStatus,
} from "@/features/automation/hooks/useAutomationPage";

const mockApiRequest = vi.mocked(apiRequest);

describe("stop generation helpers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("stop API is called with run_id", async () => {
    mockApiRequest.mockResolvedValue({
      success: true,
      status: "stopped",
      message: "Automation stopped",
      run_id: "abc",
    });

    const res = await automationApi.stop("abc");

    expect(mockApiRequest).toHaveBeenCalledWith("/automation/runs/abc/stop", {
      method: "POST",
    });
    expect(res.success).toBe(true);
    expect(res.status).toBe("stopped");
  });

  it("identifies active non-terminal run statuses for progress restoration", () => {
    // Active statuses should return true
    expect(isActiveRunStatus("running")).toBe(true);
    expect(isActiveRunStatus("paused")).toBe(true);
    expect(isActiveRunStatus("pending")).toBe(true);
    expect(isActiveRunStatus("queued")).toBe(true);
    expect(isActiveRunStatus("extracting")).toBe(true);
    expect(isActiveRunStatus("processing")).toBe(true);
    expect(isActiveRunStatus("pause_requested")).toBe(true);
    expect(isActiveRunStatus("stopping")).toBe(true);

    // Terminal statuses should return false
    expect(isActiveRunStatus("stopped")).toBe(false);
    expect(isActiveRunStatus("cancelled")).toBe(false);
    expect(isActiveRunStatus("completed")).toBe(false);
    expect(isActiveRunStatus("failed")).toBe(false);
    expect(isActiveRunStatus("idle")).toBe(false);
  });

  it("terminal statuses clear active progress polling", () => {
    expect(isTerminalRunStatus("stopped")).toBe(true);
    expect(isTerminalRunStatus("running")).toBe(false);
  });

  it("pause and resume API are called with run_id", async () => {
    mockApiRequest.mockResolvedValue({
      success: true,
      status: "pause_requested",
      message: "Pause requested",
      run_id: "abc",
    });

    await automationApi.pause("abc");
    expect(mockApiRequest).toHaveBeenCalledWith("/automation/runs/abc/pause", {
      method: "POST",
    });

    mockApiRequest.mockResolvedValue({
      success: true,
      status: "running",
      message: "Automation resumed",
      run_id: "abc",
    });
    await automationApi.resume("abc");
    expect(mockApiRequest).toHaveBeenCalledWith("/automation/runs/abc/resume", {
      method: "POST",
    });
  });

  it("engine stop fallback without run_id still uses /automation/stop", async () => {
    mockApiRequest.mockResolvedValue({
      success: true,
      status: "stopped",
      message: "Automation stopped",
    });

    await automationApi.stop();

    expect(mockApiRequest).toHaveBeenCalledWith("/automation/stop", {
      method: "POST",
    });
  });
});
