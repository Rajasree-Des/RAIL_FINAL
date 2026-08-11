/**
 * Shared date/time handling for the Dashboard, Activity Log, and Reports.
 *
 * Backend timestamps are stored in UTC. Everything here parses them as UTC
 * (even when the offset is missing) and formats them using the configured
 * display preferences (time zone, date format, 12/24-hour clock) from
 * Settings — defaults: Asia/Kolkata, DD/MM/YYYY, 12-hour.
 */

import { getDisplayPrefs, type DateFormatPref, type TimeFormatPref } from "@/utils/displayPrefs";

export const DISPLAY_TIME_ZONE = "Asia/Kolkata";

const HAS_ZONE_RE = /(Z|[+-]\d{2}:?\d{2})$/;

/** Parse a backend ISO timestamp. Strings without an offset are UTC. */
export function parseBackendTimestamp(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const date = new Date(HAS_ZONE_RE.test(iso) ? iso : `${iso}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

// Fixed offsets for the supported time zone options (used for day boundaries)
const ZONE_OFFSETS: Record<string, string> = {
  "Asia/Kolkata": "+05:30",
  UTC: "+00:00",
};

const formatterCache = new Map<string, Intl.DateTimeFormat>();

function timeFormatter(timeZone: string, timeFormat: TimeFormatPref): Intl.DateTimeFormat {
  const key = `time:${timeZone}:${timeFormat}`;
  let fmt = formatterCache.get(key);
  if (!fmt) {
    // en-US guarantees "7:33 PM"; en-GB guarantees "19:33"
    fmt =
      timeFormat === "24h"
        ? new Intl.DateTimeFormat("en-GB", {
            timeZone,
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          })
        : new Intl.DateTimeFormat("en-US", {
            timeZone,
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
          });
    formatterCache.set(key, fmt);
  }
  return fmt;
}

function dateFormatter(timeZone: string): Intl.DateTimeFormat {
  const key = `date:${timeZone}`;
  let fmt = formatterCache.get(key);
  if (!fmt) {
    fmt = new Intl.DateTimeFormat("en-CA", {
      // en-CA yields YYYY-MM-DD parts we can reorder for any format
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    formatterCache.set(key, fmt);
  }
  return fmt;
}

function dayKeyOf(date: Date, timeZone: string): string {
  return dateFormatter(timeZone).format(date);
}

function formatDatePart(date: Date, timeZone: string, dateFormat: DateFormatPref): string {
  const [year, month, day] = dateFormatter(timeZone).format(date).split("-");
  if (dateFormat === "MM/DD/YYYY") return `${month}/${day}/${year}`;
  if (dateFormat === "YYYY-MM-DD") return `${year}-${month}-${day}`;
  return `${day}/${month}/${year}`;
}

/** Time of day in the configured zone and clock, e.g. "7:33 PM" or "19:33". */
export function formatTime12h(date: Date): string {
  const prefs = getDisplayPrefs();
  return timeFormatter(prefs.timezone, prefs.timeFormat).format(date);
}

/** Date + time in the configured formats, e.g. "15/07/2026 7:33 PM". */
export function formatDateTime12h(iso: string): string {
  const date = parseBackendTimestamp(iso);
  if (!date) return iso;
  const prefs = getDisplayPrefs();
  const datePart = formatDatePart(date, prefs.timezone, prefs.dateFormat);
  return `${datePart} ${timeFormatter(prefs.timezone, prefs.timeFormat).format(date)}`;
}

/** Date only in the configured format, e.g. "15/07/2026". */
export function formatDateOnly(iso: string): string {
  const date = parseBackendTimestamp(iso);
  if (!date) return iso;
  const prefs = getDisplayPrefs();
  return formatDatePart(date, prefs.timezone, prefs.dateFormat);
}

/** Calendar day (configured zone) the instant falls on, e.g. "2026-07-15". */
export function istDayKey(date: Date): string {
  return dayKeyOf(date, getDisplayPrefs().timezone);
}

function zoneOffset(): string {
  return ZONE_OFFSETS[getDisplayPrefs().timezone] ?? "+05:30";
}

/** UTC ISO instant for 12:00:00 AM (configured zone) on the given yyyy-mm-dd date. */
export function istDayStartUtcIso(dateStr: string): string {
  return new Date(`${dateStr}T00:00:00.000${zoneOffset()}`).toISOString();
}

/** UTC ISO instant for 11:59:59.999 PM (configured zone) on the given yyyy-mm-dd date. */
export function istDayEndUtcIso(dateStr: string): string {
  return new Date(`${dateStr}T23:59:59.999${zoneOffset()}`).toISOString();
}
