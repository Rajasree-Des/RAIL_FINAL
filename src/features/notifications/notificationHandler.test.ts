import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ActivityEntry } from "@/api/activity";
import type { NotificationPrefs } from "@/utils/displayPrefs";
import {
  createNotificationCoordinatorState,
  disposeNotificationCoordinatorState,
  handleNotificationActivity,
  REPORT_DEFER_MS,
} from "./notificationHandler";

function entry(overrides: Partial<ActivityEntry> = {}): ActivityEntry {
  return {
    id: "entry-1",
    user_id: "user-1",
    action: "REPORT_COMPLETED",
    message: "Report report1 completed",
    status: "success",
    report_slug: "report1",
    run_id: "run-1",
    metadata: {},
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

const enabledPrefs: NotificationPrefs = {
  enabled: true,
  onCompletion: true,
  onFailure: true,
  sound: true,
};

describe("notificationHandler", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function createDeps() {
    return {
      showToast: vi.fn(),
      playCompletionSound: vi.fn(),
      playFailureSound: vi.fn(),
    };
  }

  it("respects master and child toggles", () => {
    const deps = createDeps();
    const state = createNotificationCoordinatorState();

    handleNotificationActivity(
      entry({ action: "AUTOMATION_COMPLETED", report_slug: null }),
      { ...enabledPrefs, enabled: false },
      deps,
      state,
    );
    expect(deps.showToast).not.toHaveBeenCalled();

    handleNotificationActivity(
      entry({ action: "AUTOMATION_COMPLETED", report_slug: null }),
      { ...enabledPrefs, onCompletion: false },
      deps,
      state,
    );
    expect(deps.showToast).not.toHaveBeenCalled();

    handleNotificationActivity(
      entry({ action: "AUTOMATION_FAILED", report_slug: null, status: "error" }),
      { ...enabledPrefs, onFailure: false },
      deps,
      state,
    );
    expect(deps.showToast).not.toHaveBeenCalled();
  });

  it("plays sounds only when sound is enabled", () => {
    const deps = createDeps();
    const state = createNotificationCoordinatorState();

    handleNotificationActivity(
      entry({ action: "AUTOMATION_COMPLETED", report_slug: null }),
      { ...enabledPrefs, sound: false },
      deps,
      state,
    );
    expect(deps.showToast).toHaveBeenCalledOnce();
    expect(deps.playCompletionSound).not.toHaveBeenCalled();
  });

  it("suppresses per-report events after automation final for the same run", () => {
    const deps = createDeps();
    const state = createNotificationCoordinatorState();

    handleNotificationActivity(
      entry({ action: "AUTOMATION_COMPLETED", report_slug: null, id: "auto-1" }),
      enabledPrefs,
      deps,
      state,
    );
    expect(deps.showToast).toHaveBeenCalledOnce();

    handleNotificationActivity(entry({ id: "report-1" }), enabledPrefs, deps, state);
    vi.advanceTimersByTime(REPORT_DEFER_MS);
    expect(deps.showToast).toHaveBeenCalledOnce();
  });

  it("notifies deferred manual report events when no automation final arrives", () => {
    const deps = createDeps();
    const state = createNotificationCoordinatorState();

    handleNotificationActivity(entry({ id: "report-manual" }), enabledPrefs, deps, state);
    expect(deps.showToast).not.toHaveBeenCalled();
    vi.advanceTimersByTime(REPORT_DEFER_MS);
    expect(deps.showToast).toHaveBeenCalledOnce();
  });

  it("skips historical entries", () => {
    const deps = createDeps();
    const subscribedAt = Date.parse("2026-07-29T10:00:00.000Z");
    const state = createNotificationCoordinatorState(subscribedAt);

    handleNotificationActivity(
      entry({
        id: "historical",
        created_at: "2026-07-29T09:59:00.000Z",
        action: "AUTOMATION_COMPLETED",
        report_slug: null,
      }),
      enabledPrefs,
      deps,
      state,
    );
    expect(deps.showToast).not.toHaveBeenCalled();
  });

  it("dedupes repeated terminal events", () => {
    const deps = createDeps();
    const state = createNotificationCoordinatorState();
    const automation = entry({
      action: "AUTOMATION_COMPLETED",
      report_slug: null,
      id: "auto-dedupe",
    });

    handleNotificationActivity(automation, enabledPrefs, deps, state);
    handleNotificationActivity(automation, enabledPrefs, deps, state);
    expect(deps.showToast).toHaveBeenCalledOnce();
  });

  it("cleans up pending timers on dispose", () => {
    const deps = createDeps();
    const state = createNotificationCoordinatorState();
    handleNotificationActivity(entry(), enabledPrefs, deps, state);
    disposeNotificationCoordinatorState(state);
    vi.advanceTimersByTime(REPORT_DEFER_MS);
    expect(deps.showToast).not.toHaveBeenCalled();
  });
});
