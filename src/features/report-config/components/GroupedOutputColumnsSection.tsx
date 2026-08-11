import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/Input";
import type { ColumnMetadata } from "../types";

interface GroupedOutputColumnsSectionProps {
  columns: ColumnMetadata[];
  selectedColumnIds: string[];
  defaultColumnIds: string[];
  onChange: (columnIds: string[]) => void;
  disabled?: boolean;
  title?: string;
  description?: string;
}

function groupColumns(columns: ColumnMetadata[]): Map<string, ColumnMetadata[]> {
  const groups = new Map<string, ColumnMetadata[]>();
  for (const column of columns) {
    const groupKey = column.groupTitle ?? column.group ?? "Columns";
    const existing = groups.get(groupKey) ?? [];
    existing.push(column);
    groups.set(groupKey, existing);
  }
  return groups;
}

export function GroupedOutputColumnsSection({
  columns,
  selectedColumnIds,
  defaultColumnIds,
  onChange,
  disabled = false,
  title = "Output Column Filters",
  description = "Choose which columns appear in preview, Excel, and PDF output.",
}: GroupedOutputColumnsSectionProps) {
  const [query, setQuery] = useState("");
  const grouped = useMemo(() => groupColumns(columns), [columns]);

  const filteredGroups = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return grouped;
    const result = new Map<string, ColumnMetadata[]>();
    for (const [title, groupColumnsList] of grouped.entries()) {
      const matches = groupColumnsList.filter((column) =>
        column.displayName.toLowerCase().includes(normalized),
      );
      if (matches.length > 0) {
        result.set(title, matches);
      }
    }
    return result;
  }, [grouped, query]);

  const allApprovedIds = useMemo(() => columns.map((column) => column.id), [columns]);

  const toggleColumn = (columnId: string, checked: boolean) => {
    if (checked) {
      onChange([...selectedColumnIds, columnId]);
      return;
    }
    onChange(selectedColumnIds.filter((id) => id !== columnId));
  };

  const selectAll = () => onChange([...allApprovedIds]);
  const clearAll = () => onChange([]);
  const resetDefault = () => onChange([...defaultColumnIds]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          <p className="mt-0.5 text-xs text-slate-500">{description}</p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
          {selectedColumnIds.length} selected
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-lg border border-rail-line px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-surface/60 disabled:opacity-50"
          onClick={selectAll}
          disabled={disabled}
        >
          Select All
        </button>
        <button
          type="button"
          className="rounded-lg border border-rail-line px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-surface/60 disabled:opacity-50"
          onClick={clearAll}
          disabled={disabled}
        >
          Clear All
        </button>
        <button
          type="button"
          className="rounded-lg border border-rail-line px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-surface/60 disabled:opacity-50"
          onClick={resetDefault}
          disabled={disabled}
        >
          Reset to Default
        </button>
      </div>

      {selectedColumnIds.length === 0 ? (
        <p className="text-xs text-amber-700">Select at least one column to generate the report.</p>
      ) : null}

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

      <div className="space-y-5">
        {Array.from(filteredGroups.entries()).map(([groupTitle, groupColumnsList]) => (
          <div key={groupTitle} className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {groupTitle}
            </h4>
            <div className="grid gap-2 sm:grid-cols-2">
              {groupColumnsList.map((column) => {
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
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
