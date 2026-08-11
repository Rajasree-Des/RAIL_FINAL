import { AlertTriangle, Copy } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";

const EDGE_COMMAND = `& "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" \`
  --remote-debugging-port=9222 \`
  --remote-debugging-address=127.0.0.1 \`
  --user-data-dir="C:\\EdgeDebug"`;

interface ChromeConnectionDialogProps {
  open: boolean;
  onClose: () => void;
  detail?: string | null;
}

export function ChromeConnectionDialog({ open, onClose, detail }: ChromeConnectionDialogProps) {
  const { showToast } = useToast();

  const copyCommand = async () => {
    try {
      await navigator.clipboard.writeText(EDGE_COMMAND);
      showToast("success", "Copied", "Edge start command copied to clipboard");
    } catch {
      showToast("error", "Copy failed", "Could not copy to clipboard");
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-6 w-6 text-amber-500" />
            <DialogTitle>Microsoft Edge Connection Required</DialogTitle>
          </div>
          <DialogDescription className="space-y-3 pt-2">
            <p>
              Report automation connects to your Microsoft Edge window on port{" "}
              <strong>9222</strong>. Normal Edge does not enable this automatically.
            </p>
            <ol className="list-decimal space-y-1 pl-5 text-sm">
              <li>
                Ensure backend (<code className="rounded bg-slate-100 px-1">http://127.0.0.1:8000</code>)
                and frontend (<code className="rounded bg-slate-100 px-1">http://127.0.0.1:5173</code>)
                are running.
              </li>
              <li>
                Run in PowerShell from the project folder:{" "}
                <code className="rounded bg-slate-100 px-1">.\scripts\start-edge.ps1</code>{" "}
                or <code className="rounded bg-slate-100 px-1">npm run dev:all</code>
              </li>
              <li>Log in to RailMadad in that Edge window.</li>
              <li>Click Generate again.</li>
            </ol>
            {detail ? (
              <p className="rounded-md bg-red-50 p-2 text-xs text-red-800">{detail}</p>
            ) : (
              <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-900">
                Microsoft Edge automation session was not found. Start Edge with remote
                debugging on port 9222.
              </p>
            )}
            <pre className="max-h-32 overflow-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100">
              {EDGE_COMMAND}
            </pre>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="secondary" onClick={() => void copyCommand()}>
            <Copy className="mr-2 h-4 w-4" />
            Copy command
          </Button>
          <Button onClick={onClose}>OK</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
