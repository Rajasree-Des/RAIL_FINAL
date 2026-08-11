import { useEffect, useRef } from "react";
import { AlertCircle, CheckCircle2, Info, Terminal, XCircle } from "lucide-react";
import type { AutomationActivityLogEntry } from "@/features/automation/types/automation";
import { cn } from "@/utils/cn";

function formatLogTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function LogLevelIcon({ level }: { level: AutomationActivityLogEntry["level"] }) {
  switch (level) {
    case "success":
      return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-green-400" />;
    case "error":
      return <XCircle className="h-3.5 w-3.5 shrink-0 text-red-400" />;
    case "warning":
      return <AlertCircle className="h-3.5 w-3.5 shrink-0 text-amber-400" />;
    default:
      return <Info className="h-3.5 w-3.5 shrink-0 text-primary/70" />;
  }
}

export interface AutomationActivityLogProps {
  entries: AutomationActivityLogEntry[];
  isLive?: boolean;
  emptyMessage?: string;
}

export function AutomationActivityLog({
  entries,
  isLive = false,
  emptyMessage = "Activity will appear here during report generation.",
}: AutomationActivityLogProps) {
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [entries]);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-950 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-200">Activity Log</span>
        </div>
        {isLive && (
          <span className="flex items-center gap-1.5 text-xs text-green-400">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
            </span>
            Live
          </span>
        )}
      </div>
      <div className="scrollbar-thin max-h-72 overflow-y-auto p-4 font-mono text-xs leading-relaxed">
        {entries.length === 0 ? (
          <p className="text-slate-500">{emptyMessage}</p>
        ) : (
          entries.map((log) => (
            <div
              key={log.id}
              className={cn(
                "mb-2 flex gap-2",
                log.level === "error" && "text-red-300",
                log.level === "warning" && "text-amber-300",
                log.level === "success" && "text-green-300",
                log.level === "info" && "text-slate-300",
              )}
            >
              <LogLevelIcon level={log.level} />
              <span className="shrink-0 text-slate-500">{formatLogTime(log.timestamp)}</span>
              <span className="min-w-0 break-words">{log.message}</span>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
