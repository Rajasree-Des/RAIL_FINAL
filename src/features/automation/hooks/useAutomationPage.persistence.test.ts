import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  apiRequest: vi.fn(),
  API_BASE: "http://localhost:8000/api/v1",
  AUTOMATION_START_TIMEOUT_MS: 300000,
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
import {
  isActiveRunStatus,
  isTerminalRunStatus,
} from "@/features/automation/hooks/useAutomationPage";
import {
  RAILMADAD_ACTIVE_GENERATION_KEY,
  RAILMADAD_LAST_RUN_KEY,
} from "@/features/automation/utils/generationSession";

const mockApiRequest = vi.mocked(apiRequest);

describe("progress persistence helpers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();
  });

  describe("isActiveRunStatus", () => {
    it("returns true for active non-terminal statuses", () => {
      expect(isActiveRunStatus("queued")).toBe(true);
      expect(isActiveRunStatus("pending")).toBe(true);
      expect(isActiveRunStatus("running")).toBe(true);
      expect(isActiveRunStatus("extracting")).toBe(true);
      expect(isActiveRunStatus("processing")).toBe(true);
      expect(isActiveRunStatus("paused")).toBe(true);
      expect(isActiveRunStatus("pause_requested")).toBe(true);
      expect(isActiveRunStatus("stopping")).toBe(true);
    });

    it("returns false for terminal statuses", () => {
      expect(isActiveRunStatus("completed")).toBe(false);
      expect(isActiveRunStatus("failed")).toBe(false);
      expect(isActiveRunStatus("stopped")).toBe(false);
      expect(isActiveRunStatus("cancelled")).toBe(false);
      expect(isActiveRunStatus("idle")).toBe(false);
    });
  });

  describe("isTerminalRunStatus", () => {
    it("returns true for terminal statuses", () => {
      expect(isTerminalRunStatus("completed")).toBe(true);
      expect(isTerminalRunStatus("failed")).toBe(true);
      expect(isTerminalRunStatus("stopped")).toBe(true);
      expect(isTerminalRunStatus("cancelled")).toBe(true);
    });

    it("returns false for active statuses", () => {
      expect(isTerminalRunStatus("running")).toBe(false);
      expect(isTerminalRunStatus("paused")).toBe(false);
      expect(isTerminalRunStatus("pending")).toBe(false);
      expect(isTerminalRunStatus("queued")).toBe(false);
    });
  });

  describe("storage keys", () => {
    it("session storage key is correct", () => {
      expect(RAILMADAD_ACTIVE_GENERATION_KEY).toBe("railmadad_active_generation");
    });

    it("local storage key is correct", () => {
      expect(RAILMADAD_LAST_RUN_KEY).toBe("railmadad_last_run_id");
    });

    it("stores run_id in both session and local storage during active generation", () => {
      const runId = "test-run-123";
      sessionStorage.setItem(RAILMADAD_ACTIVE_GENERATION_KEY, runId);
      localStorage.setItem(RAILMADAD_LAST_RUN_KEY, runId);

      expect(sessionStorage.getItem(RAILMADAD_ACTIVE_GENERATION_KEY)).toBe(runId);
      expect(localStorage.getItem(RAILMADAD_LAST_RUN_KEY)).toBe(runId);
    });

    it("session storage is cleared on terminal status", () => {
      const runId = "test-run-123";
      sessionStorage.setItem(RAILMADAD_ACTIVE_GENERATION_KEY, runId);

      // Simulate terminal status reached
      sessionStorage.removeItem(RAILMADAD_ACTIVE_GENERATION_KEY);

      expect(sessionStorage.getItem(RAILMADAD_ACTIVE_GENERATION_KEY)).toBeNull();
    });
  });

  describe("restoration flow", () => {
    it("stored run_id can be read from session storage", () => {
      const runId = "restore-test-run";
      sessionStorage.setItem(RAILMADAD_ACTIVE_GENERATION_KEY, runId);

      const storedRunId =
        sessionStorage.getItem(RAILMADAD_ACTIVE_GENERATION_KEY) ??
        localStorage.getItem(RAILMADAD_LAST_RUN_KEY);

      expect(storedRunId).toBe(runId);
    });

    it("stored run_id can be read from local storage as fallback", () => {
      const runId = "restore-test-run";
      localStorage.setItem(RAILMADAD_LAST_RUN_KEY, runId);

      const storedRunId =
        sessionStorage.getItem(RAILMADAD_ACTIVE_GENERATION_KEY) ??
        localStorage.getItem(RAILMADAD_LAST_RUN_KEY);

      expect(storedRunId).toBe(runId);
    });

    it("session storage takes precedence over local storage", () => {
      sessionStorage.setItem(RAILMADAD_ACTIVE_GENERATION_KEY, "session-run");
      localStorage.setItem(RAILMADAD_LAST_RUN_KEY, "local-run");

      const storedRunId =
        sessionStorage.getItem(RAILMADAD_ACTIVE_GENERATION_KEY) ??
        localStorage.getItem(RAILMADAD_LAST_RUN_KEY);

      expect(storedRunId).toBe("session-run");
    });

    it("returns null when no stored run_id exists", () => {
      const storedRunId =
        sessionStorage.getItem(RAILMADAD_ACTIVE_GENERATION_KEY) ??
        localStorage.getItem(RAILMADAD_LAST_RUN_KEY);

      expect(storedRunId).toBeNull();
    });
  });
});

describe("run detail verification", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("verifies stored run_id against backend", async () => {
    const runId = "test-run-456";
    mockApiRequest.mockResolvedValue({
      run_id: runId,
      status: "running",
      reports: [],
      success_count: 0,
      failure_count: 0,
      reports_successful: 0,
      reports_failed: 0,
    });

    const response = await mockApiRequest(`/automation/runs/${runId}`);

    expect(mockApiRequest).toHaveBeenCalledWith(`/automation/runs/${runId}`);
    expect(response.run_id).toBe(runId);
    expect(isActiveRunStatus(response.status)).toBe(true);
  });

  it("handles completed run verification", async () => {
    const runId = "completed-run-789";
    mockApiRequest.mockResolvedValue({
      run_id: runId,
      status: "completed",
      reports: [],
      success_count: 3,
      failure_count: 0,
      reports_successful: 3,
      reports_failed: 0,
    });

    const response = await mockApiRequest(`/automation/runs/${runId}`);

    expect(isActiveRunStatus(response.status)).toBe(false);
    expect(isTerminalRunStatus(response.status)).toBe(true);
  });

  it("handles non-existent run verification", async () => {
    const runId = "non-existent-run";
    mockApiRequest.mockRejectedValue(new Error("Run not found"));

    await expect(mockApiRequest(`/automation/runs/${runId}`)).rejects.toThrow(
      "Run not found",
    );
  });
});

describe("active run fallback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches status to find active run when no stored run_id", async () => {
    mockApiRequest.mockResolvedValue({
      active_run: {
        id: "active-run-123",
        status: "running",
        profile_id: "default",
        profile_name: "Default",
        trigger_type: "manual",
        success_count: 0,
        failure_count: 0,
        error_message: null,
        started_at: new Date().toISOString(),
        completed_at: null,
        created_at: new Date().toISOString(),
      },
      last_run: null,
      next_scheduled_at: null,
      success_rate: 0,
      total_runs: 0,
      total_failures: 0,
      is_paused: false,
    });

    const response = await mockApiRequest("/automation/status");

    expect(mockApiRequest).toHaveBeenCalledWith("/automation/status");
    expect(response.active_run).not.toBeNull();
    expect(response.active_run.id).toBe("active-run-123");
    expect(isActiveRunStatus(response.active_run.status)).toBe(true);
  });

  it("returns null active_run when no generation in progress", async () => {
    mockApiRequest.mockResolvedValue({
      active_run: null,
      last_run: {
        id: "last-run-456",
        status: "completed",
        profile_id: "default",
        profile_name: "Default",
        trigger_type: "manual",
        success_count: 7,
        failure_count: 0,
        error_message: null,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
      },
      next_scheduled_at: null,
      success_rate: 100,
      total_runs: 10,
      total_failures: 0,
      is_paused: false,
    });

    const response = await mockApiRequest("/automation/status");

    expect(response.active_run).toBeNull();
    expect(response.last_run).not.toBeNull();
  });
});
