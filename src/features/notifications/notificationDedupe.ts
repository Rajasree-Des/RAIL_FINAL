import type { ActivityEntry } from "@/api/activity";

export type TerminalKind = "success" | "failed";

const HISTORICAL_BUFFER_MS = 2000;

export interface NotificationDedupeState {
  keys: Set<string>;
  entryIds: Set<string>;
  subscribedAt: number;
}

export function createNotificationDedupeState(
  subscribedAt: number = Date.now(),
): NotificationDedupeState {
  return {
    keys: new Set(),
    entryIds: new Set(),
    subscribedAt,
  };
}

export function buildDedupeKey(
  entry: ActivityEntry,
  terminalKind: TerminalKind,
): string {
  const runId = entry.run_id ?? entry.id;
  const slug = entry.report_slug ?? "automation";
  return `${runId}:${slug}:${terminalKind}`;
}

export function isHistoricalEntry(
  entry: ActivityEntry,
  state: NotificationDedupeState,
): boolean {
  if (!entry.created_at) return false;
  const createdAt = Date.parse(entry.created_at);
  if (Number.isNaN(createdAt)) return false;
  return createdAt < state.subscribedAt - HISTORICAL_BUFFER_MS;
}

export function isDuplicateEntry(
  entry: ActivityEntry,
  terminalKind: TerminalKind,
  state: NotificationDedupeState,
): boolean {
  if (entry.id && state.entryIds.has(entry.id)) return true;
  return state.keys.has(buildDedupeKey(entry, terminalKind));
}

export function markEntryNotified(
  entry: ActivityEntry,
  terminalKind: TerminalKind,
  state: NotificationDedupeState,
): void {
  state.keys.add(buildDedupeKey(entry, terminalKind));
  if (entry.id) state.entryIds.add(entry.id);
}
