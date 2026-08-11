/**
 * App-wide display preferences, loaded from GET /settings/display.
 *
 * Holds a module-level snapshot with sensible defaults so formatters work
 * before the fetch completes. Subscribers (React via useSyncExternalStore,
 * or plain listeners) are notified whenever the snapshot changes.
 */

import { apiRequest } from "@/api/client";

export type DateFormatPref = "DD/MM/YYYY" | "MM/DD/YYYY" | "YYYY-MM-DD";
export type TimeFormatPref = "12h" | "24h";

export interface NotificationPrefs {
  enabled: boolean;
  onCompletion: boolean;
  onFailure: boolean;
  sound: boolean;
}

export interface DisplayPrefs {
  organizationName: string;
  timezone: string;
  dateFormat: DateFormatPref;
  timeFormat: TimeFormatPref;
  pageSize: number;
  notifications: NotificationPrefs;
}

export const DEFAULT_DISPLAY_PREFS: DisplayPrefs = {
  organizationName: "South Central Railway",
  timezone: "Asia/Kolkata",
  dateFormat: "DD/MM/YYYY",
  timeFormat: "12h",
  pageSize: 50,
  notifications: {
    enabled: true,
    onCompletion: true,
    onFailure: true,
    sound: false,
  },
};

interface DisplaySettingsResponse {
  organization_name: string;
  timezone: string;
  date_format: string;
  time_format: string;
  default_page_size: number;
  enable_notifications: boolean;
  notify_on_completion: boolean;
  notify_on_failure: boolean;
  notification_sound: boolean;
}

let current: DisplayPrefs = DEFAULT_DISPLAY_PREFS;
const listeners = new Set<() => void>();

export function getDisplayPrefs(): DisplayPrefs {
  return current;
}

export function subscribeDisplayPrefs(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function setPrefs(next: DisplayPrefs) {
  if (JSON.stringify(next) === JSON.stringify(current)) return;
  current = next;
  for (const listener of listeners) listener();
}

function normalizeDateFormat(value: string): DateFormatPref {
  return value === "MM/DD/YYYY" || value === "YYYY-MM-DD" ? value : "DD/MM/YYYY";
}

/** Fetch resolved settings from the backend and update the snapshot. */
export async function loadDisplayPrefs(): Promise<void> {
  try {
    const data = await apiRequest<DisplaySettingsResponse>("/settings/display");
    setPrefs({
      organizationName: data.organization_name || DEFAULT_DISPLAY_PREFS.organizationName,
      timezone: data.timezone || DEFAULT_DISPLAY_PREFS.timezone,
      dateFormat: normalizeDateFormat(data.date_format),
      timeFormat: data.time_format === "24h" ? "24h" : "12h",
      pageSize: Number(data.default_page_size) || DEFAULT_DISPLAY_PREFS.pageSize,
      notifications: {
        enabled: !!data.enable_notifications,
        onCompletion: !!data.notify_on_completion,
        onFailure: !!data.notify_on_failure,
        sound: !!data.notification_sound,
      },
    });
  } catch {
    // Keep the current snapshot (defaults or last good values)
  }
}

/** Restore defaults (on logout / session expiry). */
export function resetDisplayPrefs(): void {
  setPrefs(DEFAULT_DISPLAY_PREFS);
}

/** Test-only: set prefs directly. */
export function __setDisplayPrefsForTest(prefs: Partial<DisplayPrefs>): void {
  setPrefs({ ...DEFAULT_DISPLAY_PREFS, ...prefs });
}
