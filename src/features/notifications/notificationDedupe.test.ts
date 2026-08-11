import { describe, expect, it } from "vitest";
import type { ActivityEntry } from "@/api/activity";
import {
  buildDedupeKey,
  createNotificationDedupeState,
  isDuplicateEntry,
  isHistoricalEntry,
  markEntryNotified,
} from "./notificationDedupe";

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

describe("notificationDedupe", () => {
  it("builds dedupe keys with automation slug fallback", () => {
    expect(buildDedupeKey(entry(), "success")).toBe("run-1:report1:success");
    expect(
      buildDedupeKey(entry({ report_slug: null, run_id: "run-2" }), "failed"),
    ).toBe("run-2:automation:failed");
  });

  it("blocks duplicate keys and entry ids", () => {
    const state = createNotificationDedupeState();
    const item = entry();

    expect(isDuplicateEntry(item, "success", state)).toBe(false);
    markEntryNotified(item, "success", state);
    expect(isDuplicateEntry(item, "success", state)).toBe(true);
  });

  it("treats entries before subscribedAt buffer as historical", () => {
    const subscribedAt = Date.parse("2026-07-29T10:00:00.000Z");
    const state = createNotificationDedupeState(subscribedAt);

    expect(
      isHistoricalEntry(
        entry({ created_at: "2026-07-29T09:59:57.999Z" }),
        state,
      ),
    ).toBe(true);
    expect(
      isHistoricalEntry(
        entry({ created_at: "2026-07-29T09:59:59.500Z" }),
        state,
      ),
    ).toBe(false);
  });
});
