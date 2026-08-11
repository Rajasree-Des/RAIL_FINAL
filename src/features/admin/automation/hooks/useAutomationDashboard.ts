import { useCallback, useEffect, useState } from "react";
import {
  automationApi,
  type AutomationLogEntry,
  type AutomationRunSummary,
  type AutomationStartResult,
  type AutomationStatus,
} from "@/api/automation";
import { checkServicesBeforeAutomation } from "@/api/connectivity";
import { ApiError } from "@/api/client";
import { useToast } from "@/components/ui/Toast";

export function useAutomationDashboard(pollIntervalMs = 5000) {
  const { showToast } = useToast();
  const [status, setStatus] = useState<AutomationStatus | null>(null);
  const [history, setHistory] = useState<AutomationRunSummary[]>([]);
  const [logs, setLogs] = useState<AutomationLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [statusRes, historyRes, logsRes] = await Promise.all([
        automationApi.getStatus(),
        automationApi.getHistory(10),
        automationApi.getLogs(),
      ]);
      setStatus(statusRes);
      setHistory(historyRes.runs);
      setLogs(logsRes.logs);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), pollIntervalMs);
    return () => clearInterval(id);
  }, [refresh, pollIntervalMs]);

  const runNow = useCallback(async () => {
    setActing(true);
    try {
      const res = await automationApi.run();
      showToast("success", "Report generation started", res.message);
      await refresh();
    } catch {
      showToast("error", "Failed to start report generation");
    } finally {
      setActing(false);
    }
  }, [refresh, showToast]);

  const startInProcess = useCallback(
    async (options?: {
      report_slugs?: string[];
      async_mode?: boolean;
      date_from?: string;
      date_to?: string;
    }): Promise<AutomationStartResult | null> => {
      setActing(true);
      try {
        const serviceCheck = await checkServicesBeforeAutomation();
        if (!serviceCheck.ok) {
          showToast("error", "Service unavailable", serviceCheck.message);
          return {
            success: false,
            connected: false,
            tab_found: false,
            error: serviceCheck.message,
            error_code: "SERVICE_UNAVAILABLE",
          };
        }

        const result = await automationApi.start(options);

        if (result.error_code === "RAILMADAD_NOT_LOGGED_IN") {
          return result;
        }

        if (options?.async_mode && result.run_id) {
          showToast("success", "Automation started", `Run ${result.run_id}`);
          await refresh();
          return result;
        }

        if (options?.async_mode && !result.success) {
          showToast(
            "error",
            "Cannot start automation",
            result.error ?? "Microsoft Edge is not connected for report generation",
          );
          await refresh();
          return result;
        }

        if (result.success) {
          showToast(
            "success",
            "Connected to RailMadad",
            result.title ?? result.url ?? undefined,
          );
        } else {
          showToast(
            "error",
            "Playwright connection failed",
            result.error ?? "Could not complete RailMadad automation",
          );
        }
        return result;
      } catch (error) {
        if (error instanceof ApiError) {
          showToast("error", "Automation request failed", error.message);
        } else if (error instanceof DOMException && error.name === "AbortError") {
          showToast(
            "error",
            "Automation timed out",
            "Report generation is still running in Microsoft Edge. Check backend logs.",
          );
        } else {
          showToast(
            "error",
            "Failed to reach backend",
            "Ensure the API server is running on http://127.0.0.1:8000",
          );
        }
        return null;
      } finally {
        setActing(false);
      }
    },
    [refresh, showToast],
  );

  const pause = useCallback(async (runId?: string): Promise<boolean> => {
    try {
      const res = await automationApi.pause(runId);
      if (!res.success) {
        showToast("error", "Failed to pause", res.message);
        return false;
      }
      showToast("info", "Report generation paused");
      void refresh();
      return true;
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Failed to pause";
      showToast("error", "Failed to pause", message);
      return false;
    }
  }, [refresh, showToast]);

  const resume = useCallback(async (runId?: string): Promise<boolean> => {
    try {
      const res = await automationApi.resume(runId);
      if (!res.success) {
        showToast("error", "Failed to resume", res.message);
        return false;
      }
      showToast("success", "Report generation resumed");
      void refresh();
      return true;
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Failed to resume";
      showToast("error", "Failed to resume", message);
      return false;
    }
  }, [refresh, showToast]);

  const stop = useCallback(async (runId?: string): Promise<boolean> => {
    setActing(true);
    try {
      const res = await automationApi.stop(runId);
      if (!res.success && res.status === "not_found") {
        showToast("error", "Failed to stop", res.message);
        return false;
      }
      showToast("warning", "Report generation stopped");
      await refresh();
      return true;
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Failed to stop";
      showToast("error", "Failed to stop", message);
      return false;
    } finally {
      setActing(false);
    }
  }, [refresh, showToast]);

  const isActive = status?.active_run != null;
  const isRunning = status?.active_run?.status === "running";
  const isPaused = status?.is_paused ?? false;

  return {
    status,
    history,
    logs,
    loading,
    acting,
    isActive,
    isRunning,
    isPaused,
    runNow,
    startInProcess,
    stop,
    pause,
    resume,
    refresh,
  };
}
