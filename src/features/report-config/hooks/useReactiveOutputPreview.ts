import { useEffect, useRef, useState } from "react";
import { isAbortError, PREVIEW_TIMEOUT_MS } from "@/api/client";
import { reportsApi, type SectionPreview } from "@/api/reports";

const DEBOUNCE_MS = 300;

interface UseReactiveOutputPreviewOptions {
  reportId: string;
  selectedColumnIds: string[];
  enabled?: boolean;
}

interface ReactivePreviewState {
  previewData: Record<string, string | number>[];
  previewColumns: Array<{ key: string; header: string }>;
  previewSections: SectionPreview[];
  emptyMessage: string;
  loading: boolean;
}

const REACTIVE_REPORT_IDS = new Set([
  "merging",
  "division",
  "scr-train",
  "scr-station",
  "train-no",
  "types",
]);

export function usesReactiveOutputPreview(reportId: string): boolean {
  return REACTIVE_REPORT_IDS.has(reportId);
}

export function useReactiveOutputPreview({
  reportId,
  selectedColumnIds,
  enabled = true,
}: UseReactiveOutputPreviewOptions): ReactivePreviewState {
  const [previewData, setPreviewData] = useState<Record<string, string | number>[]>([]);
  const [previewColumns, setPreviewColumns] = useState<Array<{ key: string; header: string }>>(
    [],
  );
  const [previewSections, setPreviewSections] = useState<SectionPreview[]>([]);
  const [emptyMessage, setEmptyMessage] = useState(
    "No generated report data is available for preview.",
  );
  const [loading, setLoading] = useState(false);
  const requestSeq = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!enabled || !usesReactiveOutputPreview(reportId)) {
      return;
    }

    if (selectedColumnIds.length === 0) {
      abortControllerRef.current?.abort();
      setPreviewData([]);
      setPreviewColumns([]);
      setPreviewSections([]);
      setEmptyMessage("Select at least one column to preview output.");
      setLoading(false);
      return;
    }

    const seq = ++requestSeq.current;
    const timer = window.setTimeout(() => {
      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setLoading(true);
      void reportsApi
        .outputPreview(
          reportId,
          {
            selected_column_ids: selectedColumnIds,
            column_order: selectedColumnIds,
          },
          { signal: controller.signal, timeoutMs: PREVIEW_TIMEOUT_MS },
        )
        .then((response) => {
          if (seq !== requestSeq.current) return;
          if (!response.available) {
            setPreviewData([]);
            setPreviewColumns([]);
            setPreviewSections([]);
            setEmptyMessage(
              response.message ?? "No generated report data is available for preview.",
            );
            return;
          }
          const columns = response.visible_columns.map((header) => ({
            key: header,
            header,
          }));
          setPreviewColumns(columns);
          setPreviewData(response.preview_rows ?? []);
          setPreviewSections(response.sections ?? []);
          setEmptyMessage("");
        })
        .catch((err) => {
          if (seq !== requestSeq.current) return;
          if (isAbortError(err)) {
            return;
          }
          setPreviewData([]);
          setPreviewColumns([]);
          setPreviewSections([]);
          setEmptyMessage(err instanceof Error ? err.message : "Preview failed.");
        })
        .finally(() => {
          if (seq === requestSeq.current) {
            setLoading(false);
          }
        });
    }, DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
      abortControllerRef.current?.abort();
    };
  }, [enabled, reportId, selectedColumnIds]);

  return { previewData, previewColumns, previewSections, emptyMessage, loading };
}
