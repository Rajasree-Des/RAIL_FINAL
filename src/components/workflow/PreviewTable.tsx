import { Table, Eye } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn } from "@/utils/cn";

interface Column {
  key: string;
  header: string;
  width?: string;
}

interface PreviewTableProps {
  title?: string;
  description?: string;
  columns: Column[];
  data: Record<string, string | number>[];
  maxRows?: number;
  emptyMessage?: string;
}

export function PreviewTable({
  title = "Data Preview",
  description = "Preview of uploaded data",
  columns,
  data,
  maxRows = 10,
  emptyMessage = "No data to preview. Upload a file to get started.",
}: PreviewTableProps) {
  const displayData = data.slice(0, maxRows);
  const hasMore = data.length > maxRows;

  return (
    <Card className="hover:shadow-premium">
      <CardHeader className="border-b border-rail-line">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-surface">
            <Eye className="h-4 w-4 text-rail-muted" />
          </div>
          <div>
            <CardTitle>{title}</CardTitle>
            <CardDescription>
              {description}
              {data.length > 0 && (
                <span className="ml-1">
                  ({displayData.length} of {data.length} rows)
                </span>
              )}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardBody className="p-0">
        {data.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={Table}
              title="No data available"
              description={emptyMessage}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-surface/95 backdrop-blur-sm">
                <tr className="border-b border-rail-line">
                  {columns.map((col) => (
                    <th
                      key={col.key}
                      className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-rail-muted"
                      style={{ width: col.width }}
                    >
                      {col.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayData.map((row, rowIndex) => (
                  <tr
                    key={rowIndex}
                    className={cn(
                      "border-b border-rail-line/60 transition-colors duration-200 last:border-0",
                      rowIndex % 2 === 0 ? "bg-white" : "bg-surface/40",
                      "hover:bg-primary/[0.03]",
                    )}
                  >
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        className="whitespace-nowrap px-5 py-3 text-rail-ink"
                      >
                        {row[col.key] ?? "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {hasMore && (
              <p className="border-t border-rail-line py-3 text-center text-xs text-rail-muted">
                Showing first {maxRows} rows. {data.length - maxRows} more rows hidden.
              </p>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
