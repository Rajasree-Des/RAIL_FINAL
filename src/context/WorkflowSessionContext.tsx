import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { GeneratedSummary, ReportSourceId } from "@/types/workflow";

type WorkflowSessionContextValue = {
  completedReports: Set<ReportSourceId>;
  markReportComplete: (id: ReportSourceId) => void;
  generatedSummary: GeneratedSummary | null;
  setGeneratedSummary: (summary: GeneratedSummary | null) => void;
  resetSession: () => void;
};

const WorkflowSessionContext = createContext<WorkflowSessionContextValue | null>(null);

export function WorkflowSessionProvider({ children }: { children: ReactNode }) {
  const [completedReports, setCompletedReports] = useState<Set<ReportSourceId>>(new Set());
  const [generatedSummary, setGeneratedSummary] = useState<GeneratedSummary | null>(null);

  const markReportComplete = useCallback((id: ReportSourceId) => {
    setCompletedReports((current) => new Set([...current, id]));
  }, []);

  const resetSession = useCallback(() => {
    setCompletedReports(new Set());
    setGeneratedSummary(null);
  }, []);

  const value = useMemo(
    () => ({
      completedReports,
      markReportComplete,
      generatedSummary,
      setGeneratedSummary,
      resetSession,
    }),
    [completedReports, markReportComplete, generatedSummary, resetSession],
  );

  return <WorkflowSessionContext.Provider value={value}>{children}</WorkflowSessionContext.Provider>;
}

export function useWorkflowSession() {
  const context = useContext(WorkflowSessionContext);
  if (!context) {
    throw new Error("useWorkflowSession must be used within WorkflowSessionProvider");
  }
  return context;
}
