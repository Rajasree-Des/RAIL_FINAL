import { apiRequest, API_BASE } from "./client";

export type ActivityStatus = "success" | "error" | "warning" | "info";

export interface ActivityEntry {
  id: string;
  user_id: string;
  action: string;
  message: string;
  status: ActivityStatus;
  report_slug: string | null;
  run_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ActivityListResponse {
  items: ActivityEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface ActivityRecentResponse {
  items: ActivityEntry[];
}

export interface ActivityListParams {
  limit?: number;
  offset?: number;
  status?: string;
  report_slug?: string;
  from?: string;
  to?: string;
}

function buildQuery(params: ActivityListParams): string {
  const search = new URLSearchParams();
  if (params.limit != null) search.set("limit", String(params.limit));
  if (params.offset != null) search.set("offset", String(params.offset));
  if (params.status) search.set("status", params.status);
  if (params.report_slug) search.set("report_slug", params.report_slug);
  if (params.from) search.set("from", params.from);
  if (params.to) search.set("to", params.to);
  const q = search.toString();
  return q ? `?${q}` : "";
}

const openStreams = new Set<EventSource>();
const openSubscriptions = new Set<ActivitySubscription>();

export function closeAllActivityStreams(): void {
  for (const subscription of openSubscriptions) {
    subscription.close();
  }
  openSubscriptions.clear();
  for (const source of openStreams) {
    source.close();
  }
  openStreams.clear();
}

export function openActivityStream(options?: {
  afterId?: string;
  onEvent?: (entry: ActivityEntry) => void;
  onError?: (error: Event) => void;
}): EventSource {
  const params = new URLSearchParams();
  if (options?.afterId) {
    params.set("after_id", options.afterId);
  }
  const qs = params.toString();
  const url = `${API_BASE}/activity/stream${qs ? `?${qs}` : ""}`;
  const source = new EventSource(url, { withCredentials: true });
  openStreams.add(source);

  source.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as ActivityEntry;
      options?.onEvent?.(data);
    } catch {
      // ignore malformed payloads
    }
  };

  source.onerror = (error) => {
    options?.onError?.(error);
  };

  const originalClose = source.close.bind(source);
  source.close = () => {
    openStreams.delete(source);
    originalClose();
  };

  return source;
}

export const activityApi = {
  list(params: ActivityListParams = {}): Promise<ActivityListResponse> {
    return apiRequest<ActivityListResponse>(`/activity${buildQuery(params)}`);
  },

  recent(limit = 10): Promise<ActivityRecentResponse> {
    return apiRequest<ActivityRecentResponse>(`/activity/recent?limit=${limit}`);
  },
};

export type ActivityTransportMode = "sse" | "polling";

export interface ActivitySubscription {
  close(): void;
}

export interface SubscribeActivityOptions {
  onEvent: (entry: ActivityEntry) => void;
  onModeChange?: (mode: ActivityTransportMode) => void;
  afterId?: string;
  /** Polling cadence when SSE is unavailable (default 7s). */
  pollIntervalMs?: number;
  /** Consecutive SSE errors before falling back to polling (default 3). */
  maxSseErrors?: number;
  /** How often to retry SSE while polling (default 30s). */
  sseRetryMs?: number;
}

const SEEN_LIMIT = 500;

/**
 * Live activity subscription: SSE first, automatic polling fallback.
 *
 * Read-only on both paths, so reconnects and polling can never create
 * duplicate rows; a bounded seen-id set prevents duplicate UI events.
 */
export function subscribeActivity(
  options: SubscribeActivityOptions,
): ActivitySubscription {
  const pollIntervalMs = options.pollIntervalMs ?? 7000;
  const maxSseErrors = options.maxSseErrors ?? 3;
  const sseRetryMs = options.sseRetryMs ?? 30_000;

  let closed = false;
  let source: EventSource | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let sseRetryTimer: ReturnType<typeof setInterval> | null = null;
  let sseErrorCount = 0;
  let lastEventId: string | undefined = options.afterId;
  const seen = new Set<string>();

  const remember = (id: string) => {
    seen.add(id);
    if (seen.size > SEEN_LIMIT) {
      const oldest = seen.values().next().value;
      if (oldest !== undefined) seen.delete(oldest);
    }
  };

  const handleEntry = (entry: ActivityEntry) => {
    if (closed) return;
    if (entry.id) {
      if (seen.has(entry.id)) return;
      remember(entry.id);
      lastEventId = entry.id;
    }
    options.onEvent(entry);
  };

  const stopPolling = () => {
    if (pollTimer != null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    if (sseRetryTimer != null) {
      clearInterval(sseRetryTimer);
      sseRetryTimer = null;
    }
  };

  const poll = async () => {
    if (closed) return;
    try {
      const res = await activityApi.list({ limit: 25 });
      // API returns newest first; emit oldest → newest for natural ordering
      for (const entry of [...res.items].reverse()) {
        handleEntry(entry);
      }
    } catch {
      // keep polling; auth failures surface via the client's session handling
    }
  };

  const startPolling = () => {
    if (closed || pollTimer != null) return;
    options.onModeChange?.("polling");
    void poll();
    pollTimer = setInterval(() => void poll(), pollIntervalMs);
    sseRetryTimer = setInterval(() => openSse(), sseRetryMs);
  };

  const openSse = () => {
    if (closed) return;
    if (typeof EventSource === "undefined") {
      startPolling();
      return;
    }
    source?.close();
    source = openActivityStream({
      afterId: lastEventId,
      onEvent: (entry) => {
        sseErrorCount = 0;
        if (pollTimer != null) {
          stopPolling();
          options.onModeChange?.("sse");
        }
        handleEntry(entry);
      },
      onError: () => {
        sseErrorCount += 1;
        if (sseErrorCount >= maxSseErrors && pollTimer == null) {
          source?.close();
          source = null;
          startPolling();
        }
      },
    });
    source.onopen = () => {
      sseErrorCount = 0;
      if (pollTimer != null) {
        stopPolling();
        options.onModeChange?.("sse");
      }
    };
  };

  const subscription: ActivitySubscription = {
    close() {
      if (closed) return;
      closed = true;
      source?.close();
      source = null;
      stopPolling();
      openSubscriptions.delete(subscription);
    },
  };
  openSubscriptions.add(subscription);
  openSse();
  return subscription;
}
