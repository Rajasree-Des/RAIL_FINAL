import { Spinner } from "@/components/ui/Spinner";
import { AutomationWorkspace } from "@/features/automation/components/AutomationWorkspace";
import { useAutomationPage } from "@/features/automation/hooks/useAutomationPage";

export function AutomationPage() {
  const page = useAutomationPage();

  if (page.loading) {
    return (
      <div className="flex justify-center py-24">
        <Spinner size="lg" />
      </div>
    );
  }

  const { loading: _loading, handlePlaywrightEvent: _handler, ...workspaceProps } = page;

  return <AutomationWorkspace {...workspaceProps} />;
}
