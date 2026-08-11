import { Navigate, useParams } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { useWorkflowConfig } from "@/context/WorkflowConfigContext";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/ui/Spinner";
import { MergingPanel } from "@/features/workflows/MergingPanel";
import { ReportPanel } from "@/features/workflows/ReportPanel";
import { SummaryPanel } from "@/features/workflows/SummaryPanel";

function LoadingState() {
  return (
    <div
      className="flex min-h-[400px] flex-col items-center justify-center"
      role="status"
      aria-live="polite"
    >
      <Spinner size="lg" />
      <p className="mt-4 text-sm text-slate-500">Loading workflow...</p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="mx-auto max-w-xl py-12">
      <Alert variant="error" title="Unable to load workflow">
        {message}
      </Alert>
    </div>
  );
}

function NotFoundState() {
  return (
    <div className="flex min-h-[400px] flex-col items-center justify-center text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-slate-100">
        <AlertCircle size={32} className="text-slate-400" />
      </div>
      <h2 className="text-lg font-semibold text-slate-900">
        Workflow not found
      </h2>
      <p className="mt-1 text-sm text-slate-500">
        The requested workflow does not exist. Please select a workflow from the sidebar.
      </p>
    </div>
  );
}

export function WorkflowPage() {
  const { workflowId } = useParams();
  const { getWorkflow, loading, error } = useWorkflowConfig();
  const workflow = workflowId ? getWorkflow(workflowId) : undefined;

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  if (!workflowId) {
    return <Navigate to="/workflows/merging" replace />;
  }

  if (!workflow) {
    return <NotFoundState />;
  }

  return (
    <article className="mx-auto max-w-4xl">
      {/* Page Header */}
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          {workflow.name}
        </h1>
        <p className="mt-2 text-base leading-relaxed text-slate-600">
          {workflow.description}
        </p>
      </header>

      {/* Workflow Content */}
      <div className="space-y-6">
        {workflow.variant === "merge" ? <MergingPanel workflow={workflow} /> : null}
        {workflow.variant === "report" ? <ReportPanel workflow={workflow} /> : null}
        {workflow.variant === "summary" ? <SummaryPanel workflow={workflow} /> : null}
      </div>
    </article>
  );
}
