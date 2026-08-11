import { Outlet } from "react-router-dom";
import { WorkflowConfigProvider } from "@/context/WorkflowConfigContext";

/** Loads workflow API config only for workflow routes (not global app boot). */
export function WorkflowLayout() {
  return (
    <WorkflowConfigProvider>
      <Outlet />
    </WorkflowConfigProvider>
  );
}
