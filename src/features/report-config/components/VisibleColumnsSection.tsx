import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/Input";
import type { ColumnMetadata } from "../types";

interface VisibleColumnsSectionProps {
  columns: ColumnMetadata[];
  selectedColumnIds: string[];
  onChange: (columnIds: string[]) => void;
  disabled?: boolean;
}

export function VisibleColumnsSection({
  columns,
  selectedColumnIds,
  onChange,
  disabled = false,
}: VisibleColumnsSectionProps) {
  const [query, setQuery] = useState("");

  const filteredColumns = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return columns;
    return columns.filter((column) =>
      column.displayName.toLowerCase().includes(normalized),
    );
  }, [columns, query]);

  const toggleColumn = (columnId: string, checked: boolean) => {
    if (checked) {
      onChange([...selectedColumnIds, columnId]);
      return;
    }
    onChange(selectedColumnIds.filter((id) => id !== columnId));
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">Visible Columns</h3>
        <p className="mt-0.5 text-xs text-slate-500">
          Choose which columns appear in the generated report. Filtering always uses the full
          original dataset.
        </p>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search columns..."
          className="pl-9"
          disabled={disabled}
        />
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {filteredColumns.map((column) => {
          const checked = selectedColumnIds.includes(column.id);
          return (
            <label
              key={column.id}
              className="flex cursor-pointer items-center gap-3 rounded-lg border border-rail-line bg-white px-3 py-2.5 text-sm hover:bg-surface/60"
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={(event) => toggleColumn(column.id, event.target.checked)}
                disabled={disabled}
                className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
              />
              <span className="flex-1 truncate text-slate-700">{column.displayName}</span>
              <span className="text-xs capitalize text-slate-400">{column.dataType}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
