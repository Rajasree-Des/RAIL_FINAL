import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";

interface DuplicateNameDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sourceName?: string;
  name: string;
  onNameChange: (value: string) => void;
  onConfirm: () => void;
  title?: string;
  nameLabel?: string;
}

export function DuplicateNameDialog({
  open,
  onOpenChange,
  sourceName,
  name,
  onNameChange,
  onConfirm,
  title = "Duplicate",
  nameLabel = "New name",
}: DuplicateNameDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {sourceName && (
            <DialogDescription>
              Create a copy of &ldquo;{sourceName}&rdquo; with a new name.
            </DialogDescription>
          )}
        </DialogHeader>
        <div className="py-4">
          <Label htmlFor="duplicate-name">{nameLabel}</Label>
          <Input
            id="duplicate-name"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="Enter name"
            className="mt-1.5"
          />
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={onConfirm} disabled={!name.trim()}>
            Duplicate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
