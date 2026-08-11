import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/api/client", () => ({
  apiRequest: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(message: string, public status: number) {
      super(message);
      this.name = "ApiError";
    }
  },
}));

import { fetchWorkflows, fetchWorkflowById } from "./workflows";
import { apiRequest, ApiError } from "@/api/client";

const mockApiRequest = vi.mocked(apiRequest);

describe("workflows API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("fetchWorkflows", () => {
    it("maps API response to domain types", async () => {
      mockApiRequest.mockResolvedValue({
        workflows: [
          {
            id: "test-workflow",
            name: "Test Workflow",
            order: 1,
            description: "Test description",
            variant: "report",
            icon: "FileCheck",
            upload_label: "Upload File",
            report_source_id: "test",
            accepted_files: [".xlsx", ".csv"],
            settings: [
              {
                id: "date",
                label: "Date",
                type: "date",
                required: true,
                placeholder: null,
                default_value: "2026-01-01",
                options: [],
                help_text: "Select a date",
              },
            ],
            preview_columns: [
              {
                key: "train",
                label: "Train",
                type: "text",
                required: true,
                source_column: null,
              },
            ],
          },
        ],
      });

      const result = await fetchWorkflows();

      expect(result).toHaveLength(1);
      expect(result[0]).toEqual({
        id: "test-workflow",
        name: "Test Workflow",
        order: 1,
        description: "Test description",
        variant: "report",
        icon: "FileCheck",
        uploadLabel: "Upload File",
        reportSourceId: "test",
        acceptedFiles: [".xlsx", ".csv"],
        settings: [
          {
            id: "date",
            label: "Date",
            type: "date",
            required: true,
            placeholder: undefined,
            defaultValue: "2026-01-01",
            options: [],
            helpText: "Select a date",
          },
        ],
        previewColumns: [
          {
            key: "train",
            label: "Train",
            type: "text",
            required: true,
          },
        ],
      });
    });

    it("handles empty workflow list", async () => {
      mockApiRequest.mockResolvedValue({ workflows: [] });

      const result = await fetchWorkflows();

      expect(result).toEqual([]);
    });

    it("handles null optional fields", async () => {
      mockApiRequest.mockResolvedValue({
        workflows: [
          {
            id: "merge",
            name: "Merge",
            order: 1,
            description: "Merge files",
            variant: "merge",
            icon: "Layers",
            upload_label: null,
            report_source_id: null,
            accepted_files: [],
            settings: [],
            preview_columns: [],
          },
        ],
      });

      const result = await fetchWorkflows();

      expect(result[0].uploadLabel).toBeUndefined();
      expect(result[0].reportSourceId).toBeUndefined();
    });
  });

  describe("fetchWorkflowById", () => {
    it("returns mapped workflow when found", async () => {
      mockApiRequest.mockResolvedValue({
        id: "test",
        name: "Test",
        order: 1,
        description: "Desc",
        variant: "report",
        icon: "FileCheck",
      });

      const result = await fetchWorkflowById("test");

      expect(result).not.toBeNull();
      expect(result?.id).toBe("test");
    });

    it("returns null when workflow not found (404)", async () => {
      mockApiRequest.mockRejectedValue(new ApiError("Not found", 404));

      const result = await fetchWorkflowById("nonexistent");

      expect(result).toBeNull();
    });

    it("throws on other errors", async () => {
      mockApiRequest.mockRejectedValue(new ApiError("Server error", 500));

      await expect(fetchWorkflowById("test")).rejects.toThrow("Server error");
    });
  });
});
