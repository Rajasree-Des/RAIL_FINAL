import { apiRequest } from "./client";
import type { DatasetMetadata } from "@/features/report-config/types";

export const datasetsApi = {
  async getMetadata(reportId: string): Promise<DatasetMetadata> {
    return apiRequest<DatasetMetadata>(`/datasets/${reportId}/metadata`);
  },

  async ingestUpload(
    reportId: string,
    payload: { uploadId: string; headerRow?: number; sheetName?: string },
  ): Promise<DatasetMetadata> {
    return apiRequest<DatasetMetadata>(`/datasets/${reportId}/ingest`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
