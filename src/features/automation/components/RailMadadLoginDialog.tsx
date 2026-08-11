import { AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";

interface RailMadadLoginDialogProps {
  open: boolean;
  onClose: () => void;
}

export function RailMadadLoginDialog({ open, onClose }: RailMadadLoginDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-6 w-6 text-amber-500" />
            <DialogTitle>RailMadad Login Required</DialogTitle>
          </div>
          <DialogDescription className="pt-2">
            Start Chrome with remote debugging enabled (port 9222), open RailMadad,
            and log in before generating reports.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button onClick={onClose}>OK</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
