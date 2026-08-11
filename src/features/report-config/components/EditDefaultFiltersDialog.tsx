import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import type { ColumnMetadata } from "../types";
import { GroupedOutputColumnsSection } from "./GroupedOutputColumnsSection";

interface EditDefaultFiltersDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  columns: ColumnMetadata[];
  /** Catalog / built-in defaults (used by Reset to Default inside the editor). */
  catalogDefaultColumnIds: string[];
  /** Currently saved user defaults. */
  savedDefaultColumnIds: string[];
  onSave: (columnIds: string[]) => Promise<void>;
  disabled?: boolean;
}

export function EditDefaultFiltersDialog({
  open,
  onOpenChange,
  columns,
  catalogDefaultColumnIds,
  savedDefaultColumnIds,
  onSave,
  disabled = false,
}: EditDefaultFiltersDialogProps) {
  const [draftIds, setDraftIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDraftIds(
      savedDefaultColumnIds.length > 0
        ? [...savedDefaultColumnIds]
        : [...catalogDefaultColumnIds],
    );
    setError(null);
    setSaving(false);
  }, [open, savedDefaultColumnIds, catalogDefaultColumnIds]);

  const handleCancel = () => {
    if (saving) return;
    onOpenChange(false);
  };

  const handleSave = async () => {
    if (draftIds.length === 0) {
      setError("Select at least one column to save as defaults.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSave(draftIds);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save default filters.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !saving && onOpenChange(next)}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Default Filters</DialogTitle>
          <DialogDescription>
            Choose which columns are enabled by default for new report runs. Per-run Output
            Column Filters remain unchanged until you reset or start a new session.
          </DialogDescription>
        </DialogHeader>

        <GroupedOutputColumnsSection
          columns={columns}
          selectedColumnIds={draftIds}
          defaultColumnIds={catalogDefaultColumnIds}
          onChange={setDraftIds}
          disabled={disabled || saving}
          title="Default column selection"
          description="These columns are enabled by default for Preview, Excel, and PDF on new report runs."
        />

        {error ? <p className="text-xs text-danger">{error}</p> : null}

        <DialogFooter>
          <Button type="button" variant="secondary" onClick={handleCancel} disabled={saving}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={() => void handleSave()}
            disabled={disabled || saving || draftIds.length === 0}
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
