import type { AutomationLogEntry } from "@/api/automation";
import type {
  ActivityLogLevel,
  AutomationActivityLogEntry,
} from "@/features/automation/types/automation";

function mapLogLevel(level: string): ActivityLogLevel {
  if (level === "error") return "error";
  if (level === "warning") return "warning";
  if (level === "success") return "success";
  return "info";
}

export function mapApiLogToActivityEntry(log: AutomationLogEntry): AutomationActivityLogEntry {
  return {
    id: `engine-${log.id}`,
    timestamp: new Date(log.created_at),
    level: mapLogLevel(log.level),
    message: log.message,
    source: "engine",
  };
}

export function mergeActivityLogs(
  pipelineLogs: AutomationActivityLogEntry[],
  apiLogs: AutomationLogEntry[],
): AutomationActivityLogEntry[] {
  const engineLogs = apiLogs.map(mapApiLogToActivityEntry);
  return [...pipelineLogs, ...engineLogs].sort(
    (a, b) => a.timestamp.getTime() - b.timestamp.getTime(),
  );
}
