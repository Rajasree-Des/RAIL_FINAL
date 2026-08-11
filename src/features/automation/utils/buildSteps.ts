import { LOGIN_STEP } from "@/features/automation/constants";
import type { AutomationReportOption, AutomationStep } from "@/features/automation/types/automation";

export function buildAutomationSteps(
  reports: AutomationReportOption[],
  selectedReportIds: string[],
): AutomationStep[] {
  const steps: AutomationStep[] = [
    { id: LOGIN_STEP.id, label: LOGIN_STEP.label, status: "waiting" },
  ];

  for (const report of reports) {
    if (selectedReportIds.includes(report.id)) {
      steps.push({ id: report.id, label: report.label, status: "waiting" });
    }
  }

  return steps;
}
