import { Eye, Table } from "lucide-react";
import { Card, CardBody, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import type { SectionPreview } from "@/api/reports";
import { PreviewTable } from "./PreviewTable";

export interface SectionedPreviewTableProps {
  title?: string;
  description?: string;
  sections: SectionPreview[];
  maxRows?: number;
  emptyMessage?: string;
}

export function SectionedPreviewTable({
  title = "Report Preview",
  description = "Preview of generated report sections",
  sections,
  maxRows = 10,
  emptyMessage = "No generated report data is available for preview.",
}: SectionedPreviewTableProps) {
  if (sections.length === 0) {
    return (
      <Card className="hover:shadow-premium">
        <CardHeader className="border-b border-rail-line">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-surface">
              <Eye className="h-4 w-4 text-rail-muted" />
            </div>
            <div>
              <CardTitle>{title}</CardTitle>
              <CardDescription>{description}</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardBody className="p-6">
          <EmptyState icon={Table} title="No data available" description={emptyMessage} />
        </CardBody>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 px-1">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-surface">
          <Eye className="h-4 w-4 text-rail-muted" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          <p className="text-xs text-slate-500">{description}</p>
        </div>
      </div>
      {sections.map((section) => {
        const columns = section.headers.map((header) => ({ key: header, header }));
        return (
          <PreviewTable
            key={section.title}
            title={section.title}
            description={
              section.empty
                ? "No data available for this section"
                : `Showing up to ${maxRows} rows`
            }
            columns={columns}
            data={section.empty ? [] : section.rows}
            maxRows={maxRows}
            emptyMessage="No data available"
          />
        );
      })}
    </div>
  );
}
