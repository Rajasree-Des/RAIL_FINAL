import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, FileSpreadsheet } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { EmptyState } from "@/components/ui/EmptyState";
import type { RowData, SpreadsheetColumn } from "@/types/workflow";

type SpreadsheetViewerProps = {
  columns: SpreadsheetColumn[];
  data?: RowData[];
  emptyMessage?: string;
};

function generateMockRows(columns: SpreadsheetColumn[], count = 28): RowData[] {
  return Array.from({ length: count }, (_, index) =>
    Object.fromEntries(
      columns.map((column) => [
        column.key,
        column.type === "number"
          ? Math.max(1, 98 - index * 3)
          : column.type === "status"
            ? index % 4 === 0
              ? "Review needed"
              : "Valid"
            : column.key === "train"
              ? `Train ${12700 + index}`
              : column.key === "division"
                ? ["HYB", "SC", "NED"][index % 3]
                : column.key === "source"
                  ? `file-${(index % 3) + 1}.xlsx`
                  : `${column.label} ${index + 1}`,
      ]),
    ),
  );
}

export function SpreadsheetViewer({
  columns,
  data,
  emptyMessage = "Upload a spreadsheet to preview data.",
}: SpreadsheetViewerProps) {
  const [globalFilter, setGlobalFilter] = useState("");
  const tableData = useMemo(() => data ?? [], [data]);
  const hasData = tableData.length > 0;

  const tableColumns = useMemo<ColumnDef<RowData>[]>(
    () =>
      columns.map((column) => ({
        accessorKey: column.key,
        header: column.label,
        cell: (info) => String(info.getValue() ?? ""),
      })),
    [columns],
  );

  const table = useReactTable({
    data: tableData,
    columns: tableColumns,
    state: { globalFilter },
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  if (!hasData) {
    return (
      <EmptyState
        icon={<FileSpreadsheet size={24} />}
        title="No data available"
        description={emptyMessage}
      />
    );
  }

  const pageInfo = `Page ${table.getState().pagination.pageIndex + 1} of ${table.getPageCount()}`;

  return (
    <div className="space-y-4">
      <Input
        aria-label="Filter spreadsheet rows"
        placeholder="Search data..."
        value={globalFilter}
        onChange={(e) => setGlobalFilter(e.target.value)}
        className="max-w-xs"
      />

      <div
        className="overflow-x-auto rounded-lg border border-slate-200 bg-white"
        role="region"
        aria-label="Spreadsheet data"
        tabIndex={0}
      >
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    scope="col"
                    className="border-b border-slate-200 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-600"
                  >
                    <button
                      type="button"
                      onClick={header.column.getToggleSortingHandler()}
                      className="hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </button>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row, rowIndex) => (
              <tr
                key={row.id}
                className={rowIndex % 2 === 0 ? "bg-white" : "bg-slate-50/50"}
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className="border-b border-slate-100 px-4 py-3 text-slate-700"
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500" aria-live="polite">
          {pageInfo}
        </p>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            aria-label="Previous page"
          >
            <ChevronLeft size={16} aria-hidden="true" />
            Previous
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            aria-label="Next page"
          >
            Next
            <ChevronRight size={16} aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}

export function generatePreviewData(
  columns: SpreadsheetColumn[],
  count = 25,
  sourceFile?: string,
): RowData[] {
  const rows = generateMockRows(columns, count);
  if (sourceFile) {
    return rows.map((row) => ({ ...row, source: sourceFile }));
  }
  return rows;
}

export function generateMergedPreviewData(
  columns: SpreadsheetColumn[],
  fileNames: string[],
): RowData[] {
  if (fileNames.length === 0) return [];
  return fileNames.flatMap((fileName, fileIndex) =>
    generateMockRows(columns, 8).map((row, rowIndex) => ({
      ...row,
      source: fileName,
      train: `Train ${12700 + fileIndex * 10 + rowIndex}`,
    })),
  );
}
