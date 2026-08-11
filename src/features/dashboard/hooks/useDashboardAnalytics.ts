import { useCallback, useEffect, useRef, useState } from "react";
import { subscribeActivity, type ActivityEntry } from "@/api/activity";
import {
  dashboardApi,
  isDashboardRelevant,
  type DashboardAnalytics,
} from "@/api/dashboard";

let cachedAnalytics: DashboardAnalytics | null = null;

/** Cleared on logout so the next account never sees stale data. */
export function clearAnalyticsCache(): void {
  cachedAnalytics = null;
}

const REFETCH_DEBOUNCE_MS = 1200;

/**
 * Analytics derived from the latest completed run's report outputs.
 * Cached across mounts; refetched (debounced) when workflow events arrive.
 */
export function useDashboardAnalytics() {
  const [analytics, setAnalytics] = useState<DashboardAnalytics | null>(
    cachedAnalytics,
  );
  const [loading, setLoading] = useState(cachedAnalytics === null);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const refetch = useCallback(async () => {
    try {
      const data = await dashboardApi.analytics();
      cachedAnalytics = data;
      if (mountedRef.current) {
        setAnalytics(data);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current && cachedAnalytics === null) {
        setError(err instanceof Error ? err.message : "Failed to load analytics");
      }
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void refetch();

    const subscription = subscribeActivity({
      onEvent: (entry: ActivityEntry) => {
        if (!isDashboardRelevant(entry.action)) return;
        if (debounceRef.current != null) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
          debounceRef.current = null;
          void refetch();
        }, REFETCH_DEBOUNCE_MS);
      },
    });

    return () => {
      mountedRef.current = false;
      if (debounceRef.current != null) clearTimeout(debounceRef.current);
      subscription.close();
    };
  }, [refetch]);

  return { analytics, loading, error, refetch };
}
