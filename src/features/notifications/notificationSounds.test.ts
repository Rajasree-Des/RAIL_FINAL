import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  __resetNotificationAudioForTest,
  playCompletionSound,
  playFailureSound,
  unlockNotificationAudio,
} from "./notificationSounds";

describe("notificationSounds", () => {
  let oscillatorFrequencies: number[] = [];

  beforeEach(() => {
    __resetNotificationAudioForTest();
    oscillatorFrequencies = [];

    class MockAudioContext {
      state = "running";
      currentTime = 0;
      destination = {};
      resume = vi.fn(async () => undefined);
      createOscillator = vi.fn(() => {
        const node = {
          type: "sine",
          frequency: {
            set value(v: number) {
              oscillatorFrequencies.push(v);
            },
            get value() {
              return oscillatorFrequencies[oscillatorFrequencies.length - 1] ?? 0;
            },
          },
          connect: vi.fn().mockReturnThis(),
          start: vi.fn(),
          stop: vi.fn(),
        };
        return node;
      });
      createGain = vi.fn(() => ({
        gain: {
          setValueAtTime: vi.fn(),
          exponentialRampToValueAtTime: vi.fn(),
        },
        connect: vi.fn().mockReturnThis(),
      }));
    }

    vi.stubGlobal("AudioContext", MockAudioContext);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    __resetNotificationAudioForTest();
  });

  it("plays different completion and failure tones", () => {
    unlockNotificationAudio();
    playCompletionSound();
    const completion = [...oscillatorFrequencies];

    oscillatorFrequencies = [];
    playFailureSound();
    const failure = [...oscillatorFrequencies];

    expect(completion).toEqual([523.25, 659.25]);
    expect(failure).toEqual([196, 146.83]);
    expect(completion).not.toEqual(failure);
  });

  it("does not fetch external assets", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    unlockNotificationAudio();
    playCompletionSound();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("unlock is safe when AudioContext is unavailable", () => {
    vi.unstubAllGlobals();
    expect(() => unlockNotificationAudio()).not.toThrow();
  });
});
