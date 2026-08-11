import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchWorkflows } from "@/api/workflows";
import type { WorkflowDefinition } from "@/types/workflow";

type WorkflowConfigContextValue = {
  workflows: WorkflowDefinition[];
  loading: boolean;
  error: string | null;
  getWorkflow: (id: string) => WorkflowDefinition | undefined;
};

const WorkflowConfigContext = createContext<WorkflowConfigContextValue | null>(null);

export function WorkflowConfigProvider({ children }: { children: ReactNode }) {
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetchWorkflows()
      .then((data) => {
        if (!cancelled) {
          setWorkflows(data);
          setLoading(false);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setWorkflows([]);
          setLoading(false);
          setError(err instanceof Error ? err.message : "Failed to load workflows");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo(
    () => ({
      workflows,
      loading,
      error,
      getWorkflow: (id: string) => workflows.find((workflow) => workflow.id === id),
    }),
    [workflows, loading, error],
  );

  return <WorkflowConfigContext.Provider value={value}>{children}</WorkflowConfigContext.Provider>;
}

export function useWorkflowConfig() {
  const context = useContext(WorkflowConfigContext);
  if (!context) {
    throw new Error("useWorkflowConfig must be used within WorkflowConfigProvider");
  }
  return context;
}
