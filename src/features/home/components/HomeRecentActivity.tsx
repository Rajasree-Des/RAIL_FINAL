import { useEffect, useState } from "react";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import {
  activityApi,
  subscribeActivity,
  type ActivityEntry,
  type ActivitySubscription,
} from "@/api/activity";
import { formatDateTime12h, parseBackendTimestamp } from "@/utils/datetime";
import { cn } from "@/utils/cn";

function formatRelativeTime(iso: string): string {
  const date = parseBackendTimestamp(iso);
  if (!date) return iso;
  const diffMs = date.getTime() - Date.now();
  const absSec = Math.round(Math.abs(diffMs) / 1000);
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (absSec < 60) return rtf.format(Math.round(diffMs / 1000), "second");
  const absMin = Math.round(absSec / 60);
  if (absMin < 60) return rtf.format(Math.round(diffMs / 60_000), "minute");
  const absHr = Math.round(absMin / 60);
  if (absHr < 48) return rtf.format(Math.round(diffMs / 3_600_000), "hour");
  return rtf.format(Math.round(diffMs / 86_400_000), "day");
}

function statusDotClass(status: ActivityEntry["status"]): string {
  switch (status) {
    case "success":
      return "bg-success";
    case "error":
      return "bg-red-500";
    case "warning":
      return "bg-amber-500";
    default:
      return "bg-primary";
  }
}

function statusRingClass(status: ActivityEntry["status"]): string {
  switch (status) {
    case "success":
      return "bg-success-muted";
    case "error":
      return "bg-red-50";
    case "warning":
      return "bg-amber-50";
    default:
      return "bg-primary-muted";
  }
}

export function HomeRecentActivity() {
  const [items, setItems] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let subscription: ActivitySubscription | null = null;

    const load = async () => {
      try {
        const res = await activityApi.recent(10);
        if (cancelled) return;
        setItems(res.items);
        const newest = res.items[0]?.id;
        subscription = subscribeActivity({
          afterId: newest,
          onEvent: (entry) => {
            setItems((prev) => {
              if (prev.some((p) => p.id === entry.id)) return prev;
              return [entry, ...prev].slice(0, 10);
            });
          },
        });
      } catch {
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();

    return () => {
      cancelled = true;
      subscription?.close();
    };
  }, []);

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-rail-ink">Recent Activity</h2>
        <p className="mt-1 text-sm text-rail-muted">Your latest account activity</p>
      </div>

      <Card className="hover:shadow-premium">
        <CardHeader className="border-b border-rail-line py-4">
          <CardTitle className="text-sm">Recent</CardTitle>
        </CardHeader>
        <CardBody className="divide-y divide-rail-line p-0">
          {loading && (
            <div className="px-6 py-8 text-sm text-rail-muted">Loading activity…</div>
          )}
          {!loading && items.length === 0 && (
            <div className="px-6 py-8 text-sm text-rail-muted">No activity yet</div>
          )}
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between px-6 py-4 transition-colors duration-200 hover:bg-surface"
            >
              <div className="flex items-center gap-3">
                <span
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full",
                    statusRingClass(item.status),
                  )}
                >
                  <span className={cn("h-2 w-2 rounded-full", statusDotClass(item.status))} />
                </span>
                <span className="text-sm font-medium text-rail-ink">{item.message}</span>
              </div>
              <time
                className="text-xs tabular-nums text-rail-muted"
                dateTime={item.created_at}
                title={formatDateTime12h(item.created_at)}
              >
                {formatRelativeTime(item.created_at)}
              </time>
            </div>
          ))}
        </CardBody>
      </Card>
    </section>
  );
}
