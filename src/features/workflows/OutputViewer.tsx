import { useState } from "react";
import { Download, FileText, Table2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SimpleTabs } from "@/components/ui/Tabs";
import { EmptyState } from "@/components/ui/EmptyState";
import { SpreadsheetViewer } from "@/features/workflows/SpreadsheetViewer";
import type { RowData, SpreadsheetColumn } from "@/types/workflow";

type OutputViewerProps = {
  tabs: string[];
  workflowName: string;
  previewColumns?: SpreadsheetColumn[];
  previewData?: RowData[];
  pdfContent?: string;
  onDownload?: (format: string) => void;
};

export function OutputViewer({
  tabs,
  workflowName,
  previewColumns = [],
  previewData,
  pdfContent,
  onDownload,
}: OutputViewerProps) {
  const [tab, setTab] = useState(tabs[0] ?? "Spreadsheet");

  const defaultPdfContent =
    pdfContent ??
    `Official ${workflowName} report prepared for competent authority review. Key observations, affected trains, complaint categories, and recommended action points are summarized for approval.`;

  const hasData = previewData && previewData.length > 0;

  return (
    <div className="space-y-4">
      <SimpleTabs tabs={tabs} active={tab} onChange={setTab} />

      <div
        id={`tabpanel-${tab.toLowerCase().replace(/\s+/g, "-")}`}
        role="tabpanel"
        aria-label={`${tab} content`}
        className="min-h-[200px]"
      >
        {tab === "Spreadsheet" ? (
          previewColumns.length > 0 ? (
            hasData ? (
              <SpreadsheetViewer
                columns={previewColumns}
                data={previewData}
                emptyMessage="Generate output to preview spreadsheet results."
              />
            ) : (
              <EmptyState
                icon={<Table2 size={24} />}
                title="No output generated"
                description="Click Generate to create the report output."
              />
            )
          ) : (
            <EmptyState
              icon={<Table2 size={24} />}
              title="Output preview"
              description="Spreadsheet output will appear here after generation."
            />
          )
        ) : null}

        {tab === "PDF Preview" ? (
          <div className="rounded-lg border border-slate-200 bg-white p-8">
            <div className="mx-auto max-w-2xl">
              <div className="mb-6 border-b border-slate-200 pb-4">
                <h3 className="text-lg font-semibold text-slate-900">
                  {workflowName}
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  Official Railway Report Document
                </p>
              </div>
              <p className="text-sm leading-7 text-slate-700">
                {defaultPdfContent}
              </p>
            </div>
          </div>
        ) : null}

        {tab === "Export" ? (
          hasData ? (
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button
                variant="secondary"
                onClick={() => onDownload?.("excel")}
                aria-label="Download merged data as Excel file"
              >
                <Download size={16} aria-hidden="true" />
                Download Excel (.xlsx)
              </Button>
              <Button
                variant="secondary"
                onClick={() => onDownload?.("csv")}
                aria-label="Download merged data as CSV file"
              >
                <Download size={16} aria-hidden="true" />
                Download CSV (.csv)
              </Button>
            </div>
          ) : (
            <EmptyState
              icon={<FileText size={24} />}
              title="No data to export"
              description="Merge files first to enable export options."
            />
          )
        ) : null}
      </div>
    </div>
  );
}
