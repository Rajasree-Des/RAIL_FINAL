/** subscribeActivity: SSE-first with polling fallback, no duplicate events. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ActivityEntry } from "./activity";

const listMock = vi.fn();

vi.mock("./client", () => ({
  API_BASE: "/api/v1",
  apiRequest: (...args: unknown[]) => listMock(...args),
}));

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  withCredentials: boolean;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  closed = false;

  constructor(url: string, init?: EventSourceInit) {
    this.url = url;
    this.withCredentials = Boolean(init?.withCredentials);
    FakeEventSource.instances.push(this);
  }

  close() {
    this.closed = true;
  }

  emit(entry: ActivityEntry) {
    this.onmessage?.({ data: JSON.stringify(entry) } as MessageEvent);
  }

  fail() {
    this.onerror?.(new Event("error"));
  }
}

function entry(id: string, action = "REPORT_COMPLETED"): ActivityEntry {
  return {
    id,
    user_id: "u1",
    action,
    message: `msg-${id}`,
    status: "success",
    report_slug: null,
    run_id: null,
    metadata: {},
    created_at: new Date().toISOString(),
  };
}

describe("subscribeActivity", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeEventSource.instances = [];
    listMock.mockReset();
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  async function makeSubscription() {
    const { subscribeActivity } = await import("./activity");
    return subscribeActivity;
  }

  it("delivers SSE events and dedupes repeated ids", async () => {
    const subscribeActivity = await makeSubscription();
    const received: string[] = [];
    const sub = subscribeActivity({ onEvent: (e) => received.push(e.id) });

    const source = FakeEventSource.instances[0];
    expect(source).toBeDefined();
    source.emit(entry("e1"));
    source.emit(entry("e1"));
    source.emit(entry("e2"));

    expect(received).toEqual(["e1", "e2"]);
    sub.close();
    expect(source.closed).toBe(true);
  });

  it("falls back to polling after repeated SSE errors without duplicating rows", async () => {
    const subscribeActivity = await makeSubscription();
    const received: string[] = [];
    const modes: string[] = [];
    listMock.mockResolvedValue({
      items: [entry("p2"), entry("p1")], // newest first, as the API returns
      total: 2,
      limit: 25,
      offset: 0,
    });

    const sub = subscribeActivity({
      onEvent: (e) => received.push(e.id),
      onModeChange: (mode) => modes.push(mode),
      pollIntervalMs: 1000,
    });

    const source = FakeEventSource.instances[0];
    source.emit(entry("p1"));
    source.fail();
    source.fail();
    source.fail();

    expect(modes).toContain("polling");
    // first poll fires immediately
    await vi.advanceTimersByTimeAsync(0);
    // p1 was already seen through SSE; only p2 is new, emitted oldest→newest
    expect(received).toEqual(["p1", "p2"]);

    // subsequent polls with identical data add nothing
    await vi.advanceTimersByTimeAsync(2500);
    expect(received).toEqual(["p1", "p2"]);
    expect(listMock).toHaveBeenCalled();

    sub.close();
  });

  it("returns to SSE when the retried stream opens", async () => {
    const subscribeActivity = await makeSubscription();
    const modes: string[] = [];
    listMock.mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 });

    const sub = subscribeActivity({
      onEvent: () => {},
      onModeChange: (mode) => modes.push(mode),
      pollIntervalMs: 1000,
      sseRetryMs: 5000,
    });

    const first = FakeEventSource.instances[0];
    first.fail();
    first.fail();
    first.fail();
    expect(modes).toContain("polling");

    // SSE retry timer opens a fresh stream
    await vi.advanceTimersByTimeAsync(5000);
    const retried = FakeEventSource.instances.at(-1);
    expect(retried).toBeDefined();
    expect(retried).not.toBe(first);
    retried!.onopen?.(new Event("open"));
    expect(modes.at(-1)).toBe("sse");

    sub.close();
  });
});
