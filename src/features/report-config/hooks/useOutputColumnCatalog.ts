import { useCallback, useEffect, useRef, useState } from "react";
import { isAbortError } from "@/api/client";
import { reportsApi } from "@/api/reports";
import type { ColumnMetadata } from "../types";

export interface OutputColumnDefinition {
  id: string;
  label: string;
  required: boolean;
  default_visible: boolean;
  group?: string;
  group_title?: string;
}

interface UseOutputColumnCatalogResult {
  columns: ColumnMetadata[];
  defaultColumnIds: string[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const OUTPUT_CATALOG_PAGE_IDS = new Set([
  "merging",
  "division",
  "scr-train",
  "scr-station",
  "train-no",
  "types",
  "report9",
  "report14",
  "report18",
]);

const REACTIVE_CATALOG_PAGE_IDS = new Set([
  "merging",
  "division",
  "scr-train",
  "scr-station",
  "train-no",
  "types",
]);

const COLUMNLESS_MANUAL_REPORTS = new Set(["bottom-report"]);

export function usesManualColumnSelection(reportId: string): boolean {
  return !COLUMNLESS_MANUAL_REPORTS.has(reportId);
}

export function usesOutputColumnCatalog(reportId: string): boolean {
  return OUTPUT_CATALOG_PAGE_IDS.has(reportId);
}

export function useOutputColumnCatalog(
  reportId: string,
  options: { enabled?: boolean } = {},
): UseOutputColumnCatalogResult {
  const enabled = (options.enabled ?? true) && usesOutputColumnCatalog(reportId);
  const [columns, setColumns] = useState<ColumnMetadata[]>([]);
  const [defaultColumnIds, setDefaultColumnIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const hadSuccessfulLoadRef = useRef(false);

  const refresh = useCallback(async () => {
    if (!enabled || !reportId) {
      setColumns([]);
      setDefaultColumnIds([]);
      setLoading(false);
      setError(null);
      hadSuccessfulLoadRef.current = false;
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload = await reportsApi.getOutputColumns(reportId);
      setColumns(
        payload.columns.map((column) => ({
          id: column.id,
          fieldName: column.id,
          displayName: column.label,
          dataType: "text" as const,
          filterable: false,
          sortable: false,
          group: column.group,
          groupTitle: column.group_title,
        })),
      );
      setDefaultColumnIds(payload.default_column_ids);
      hadSuccessfulLoadRef.current = true;
      if (reportId === "merging") {
        console.info("report1_available_columns_loaded", {
          count: payload.columns.length,
        });
      } else if (reportId === "division") {
        console.info("report2_available_columns_loaded", {
          count: payload.columns.length,
        });
      } else if (reportId === "train-no") {
        console.info("report3_available_columns_loaded", {
          count: payload.columns.length,
        });
      } else if (reportId === "types") {
        console.info("report4_available_columns_loaded", {
          count: payload.columns.length,
        });
      }
    } catch (err) {
      const transient = isAbortError(err);
      if (REACTIVE_CATALOG_PAGE_IDS.has(reportId) && transient) {
        return;
      }
      if (hadSuccessfulLoadRef.current) {
        if (!transient) {
          setError(err instanceof Error ? err.message : "Failed to load output columns");
        }
        return;
      }
      setColumns([]);
      setDefaultColumnIds([]);
      setError(err instanceof Error ? err.message : "Failed to load output columns");
    } finally {
      setLoading(false);
    }
  }, [enabled, reportId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { columns, defaultColumnIds, loading, error, refresh };
}
