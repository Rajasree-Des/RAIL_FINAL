/** UTC → IST conversion and settings-aware formatting tests. */

import { afterEach, describe, expect, it } from "vitest";
import {
  formatDateOnly,
  formatDateTime12h,
  formatTime12h,
  istDayEndUtcIso,
  istDayStartUtcIso,
  parseBackendTimestamp,
} from "./datetime";
import { __setDisplayPrefsForTest, resetDisplayPrefs } from "./displayPrefs";

afterEach(() => {
  resetDisplayPrefs();
});

describe("parseBackendTimestamp", () => {
  it("parses aware UTC timestamps", () => {
    const date = parseBackendTimestamp("2026-07-15T14:03:15+00:00");
    expect(date?.toISOString()).toBe("2026-07-15T14:03:15.000Z");
  });

  it("treats naive timestamps as UTC, not local time", () => {
    const naive = parseBackendTimestamp("2026-07-15T14:03:15");
    const aware = parseBackendTimestamp("2026-07-15T14:03:15Z");
    expect(naive?.getTime()).toBe(aware?.getTime());
  });

  it("returns null for empty or invalid input", () => {
    expect(parseBackendTimestamp("")).toBeNull();
    expect(parseBackendTimestamp(null)).toBeNull();
    expect(parseBackendTimestamp("not-a-date")).toBeNull();
  });
});

describe("IST 12-hour formatting", () => {
  it("converts UTC to IST with uppercase AM/PM (14:03 UTC → 7:33 PM)", () => {
    const date = parseBackendTimestamp("2026-07-15T14:03:15+00:00")!;
    expect(formatTime12h(date)).toBe("7:33 PM");
  });

  it("formats DD/MM/YYYY h:mm AM/PM and never 24-hour", () => {
    expect(formatDateTime12h("2026-07-15T14:03:15+00:00")).toBe(
      "15/07/2026 7:33 PM",
    );
    // UTC evening crossing into the next IST day
    expect(formatDateTime12h("2026-07-15T20:00:00Z")).toBe(
      "16/07/2026 1:30 AM",
    );
    expect(formatDateTime12h("2026-07-15T14:03:15Z")).not.toContain("19:33");
  });

  it("formats morning times with AM", () => {
    expect(formatDateTime12h("2026-07-15T02:36:00Z")).toBe(
      "15/07/2026 8:06 AM",
    );
  });
});

describe("settings-aware formatting", () => {
  it("honors the 24-hour time format setting", () => {
    __setDisplayPrefsForTest({ timeFormat: "24h" });
    expect(formatDateTime12h("2026-07-15T14:03:15Z")).toBe("15/07/2026 19:33");
    const date = parseBackendTimestamp("2026-07-15T14:03:15Z")!;
    expect(formatTime12h(date)).toBe("19:33");
  });

  it("honors alternative date formats", () => {
    __setDisplayPrefsForTest({ dateFormat: "MM/DD/YYYY" });
    expect(formatDateOnly("2026-07-15T14:03:15Z")).toBe("07/15/2026");
    __setDisplayPrefsForTest({ dateFormat: "YYYY-MM-DD" });
    expect(formatDateOnly("2026-07-15T14:03:15Z")).toBe("2026-07-15");
  });

  it("honors the UTC timezone setting", () => {
    __setDisplayPrefsForTest({ timezone: "UTC" });
    expect(formatDateTime12h("2026-07-15T14:03:15Z")).toBe("15/07/2026 2:03 PM");
    expect(istDayStartUtcIso("2026-07-15")).toBe("2026-07-15T00:00:00.000Z");
    expect(istDayEndUtcIso("2026-07-15")).toBe("2026-07-15T23:59:59.999Z");
  });
});

describe("IST day boundaries for filters", () => {
  it("From starts at 12:00:00 AM IST (18:30 UTC previous day)", () => {
    expect(istDayStartUtcIso("2026-07-15")).toBe("2026-07-14T18:30:00.000Z");
  });

  it("To covers through 11:59:59.999 PM IST", () => {
    expect(istDayEndUtcIso("2026-07-15")).toBe("2026-07-15T18:29:59.999Z");
  });

  it("boundaries bracket an event late in the IST evening (no off-by-one day)", () => {
    // 15 Jul 7:33 PM IST = 15 Jul 14:03 UTC
    const event = new Date("2026-07-15T14:03:15Z").getTime();
    expect(event).toBeGreaterThanOrEqual(
      new Date(istDayStartUtcIso("2026-07-15")).getTime(),
    );
    expect(event).toBeLessThanOrEqual(
      new Date(istDayEndUtcIso("2026-07-15")).getTime(),
    );
    // The same event is outside the previous day's range
    expect(event).toBeGreaterThan(
      new Date(istDayEndUtcIso("2026-07-14")).getTime(),
    );
  });
});
