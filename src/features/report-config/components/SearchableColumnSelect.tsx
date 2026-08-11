import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Search } from "lucide-react";
import { cn } from "@/utils/cn";
import type { ColumnMetadata } from "../types";

interface SearchableColumnSelectProps {
  columns: ColumnMetadata[];
  value: string;
  onChange: (columnId: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function SearchableColumnSelect({
  columns,
  value,
  onChange,
  disabled = false,
  placeholder = "Select column",
}: SearchableColumnSelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const selected = columns.find((column) => column.id === value);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return columns;
    return columns.filter(
      (column) =>
        column.displayName.toLowerCase().includes(normalized) ||
        column.fieldName.toLowerCase().includes(normalized),
    );
  }, [columns, query]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        className={cn(
          "flex h-10 w-full items-center justify-between rounded-md border border-slate-200 bg-white px-3 text-left text-sm",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
          disabled && "cursor-not-allowed opacity-50",
        )}
      >
        <span className={cn("truncate", !selected && "text-slate-400")}>
          {selected?.displayName ?? placeholder}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full overflow-hidden rounded-xl border border-rail-line bg-white shadow-float">
          <div className="border-b border-rail-line p-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search columns..."
                className="h-9 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                autoFocus
              />
            </div>
          </div>
          <ul className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-slate-500">No columns found</li>
            ) : (
              filtered.map((column) => (
                <li key={column.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(column.id);
                      setOpen(false);
                      setQuery("");
                    }}
                    className={cn(
                      "flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-surface",
                      column.id === value && "bg-primary/5 text-primary",
                    )}
                  >
                    <span>{column.displayName}</span>
                    <span className="text-xs capitalize text-slate-400">{column.dataType}</span>
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
