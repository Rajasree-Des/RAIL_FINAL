export { AutomationPage } from "./AutomationPage";
export { AutomationWorkspace } from "./components/AutomationWorkspace";
export type { AutomationWorkspaceProps } from "./components/AutomationWorkspace";
export { useAutomationPage } from "./hooks/useAutomationPage";
export { useAutomationRunState } from "./hooks/useAutomationRunState";
export type { UseAutomationRunStateReturn } from "./hooks/useAutomationRunState";
export { AUTOMATION_REPORTS } from "./constants";
export type {
  AutomationActivityLogEntry,
  AutomationCompletionSummary,
  AutomationReportOption,
  AutomationRunState,
  AutomationRunStatus,
  AutomationStep,
  AutomationStepStatus,
  PlaywrightAutomationEvent,
} from "./types/automation";
export { applyPlaywrightEvent } from "./utils/playwrightEvents";
