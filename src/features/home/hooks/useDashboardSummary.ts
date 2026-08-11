import { useCallback, useEffect, useRef, useState } from "react";
import { subscribeActivity, type ActivityEntry } from "@/api/activity";
import {
  dashboardApi,
  isDashboardRelevant,
  type DashboardSummary,
} from "@/api/dashboard";
import { clearAnalyticsCache } from "@/features/dashboard/hooks/useDashboardAnalytics";

let cachedSummary: DashboardSummary | null = null;

/** Cleared on logout so the next account never sees stale data. */
export function clearDashboardCache(): void {
  cachedSummary = null;
  clearAnalyticsCache();
}

const REFETCH_DEBOUNCE_MS = 800;

export function useDashboardSummary() {
  const [summary, setSummary] = useState<DashboardSummary | null>(cachedSummary);
  const [loading, setLoading] = useState(cachedSummary === null);
  const [error, setError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const refetch = useCallback(async () => {
    try {
      const data = await dashboardApi.summary();
      cachedSummary = data;
      if (mountedRef.current) {
        setSummary(data);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current && cachedSummary === null) {
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
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

  return { summary, loading, error, refetch };
}
