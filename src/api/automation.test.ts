import { describe, expect, it } from "vitest";
import { automationApi } from "@/api/automation";

describe("automationApi.resolveApiUrl", () => {
  it("keeps absolute http URLs unchanged", () => {
    expect(
      automationApi.resolveApiUrl("http://127.0.0.1:8000/api/v1/automation/artifacts/a/preview"),
    ).toBe("http://127.0.0.1:8000/api/v1/automation/artifacts/a/preview");
  });

  it("normalizes /api/v1 paths through API_BASE", () => {
    expect(
      automationApi.resolveApiUrl("/api/v1/automation/artifacts/a/preview"),
    ).toBe("/api/v1/automation/artifacts/a/preview");
  });

  it("prefixes bare relative paths with API_BASE", () => {
    expect(automationApi.resolveApiUrl("automation/artifacts/a/preview")).toBe(
      "/api/v1/automation/artifacts/a/preview",
    );
  });
});

describe("automationApi.withCacheBust", () => {
  it("appends artifact and run query params", () => {
    const url = automationApi.withCacheBust(
      "/api/v1/automation/artifacts/a/preview",
      "a",
      "run-1",
    );
    expect(url).toContain("v=a");
    expect(url).toContain("run_id=run-1");
  });
});
