import { useCallback, useEffect, useState } from "react";
import { datasetsApi } from "@/api/datasets";
import type { DatasetMetadata } from "@/features/report-config/types";

interface UseDatasetMetadataOptions {
  enabled?: boolean;
}

interface UseDatasetMetadataResult {
  metadata: DatasetMetadata | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useDatasetMetadata(
  reportId: string,
  options: UseDatasetMetadataOptions = {},
): UseDatasetMetadataResult {
  const enabled = options.enabled ?? Boolean(reportId);
  const [metadata, setMetadata] = useState<DatasetMetadata | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled || !reportId) {
      setMetadata(null);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await datasetsApi.getMetadata(reportId);
      setMetadata(data);
    } catch (err) {
      setMetadata(null);
      setError(err instanceof Error ? err.message : "Failed to load dataset metadata");
    } finally {
      setLoading(false);
    }
  }, [enabled, reportId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { metadata, loading, error, refresh };
}
