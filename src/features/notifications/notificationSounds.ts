let audioContext: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  try {
    if (!audioContext) {
      audioContext = new AudioContext();
    }
    if (audioContext.state === "suspended") {
      void audioContext.resume();
    }
    return audioContext;
  } catch {
    return null;
  }
}

function playTwoTone(
  frequencies: [number, number],
  durationMs: number,
  volume = 0.08,
): void {
  const ctx = getAudioContext();
  if (!ctx) return;

  const now = ctx.currentTime;
  const segment = durationMs / 2000;

  frequencies.forEach((frequency, index) => {
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = frequency;
    const start = now + index * segment;
    gain.gain.setValueAtTime(volume, start);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + segment);
    oscillator.connect(gain).connect(ctx.destination);
    oscillator.start(start);
    oscillator.stop(start + segment + 0.01);
  });
}

export function unlockNotificationAudio(): void {
  try {
    getAudioContext();
  } catch {
    // Autoplay policy or missing audio device — ignore
  }
}

export function playCompletionSound(): void {
  try {
    playTwoTone([523.25, 659.25], 350);
  } catch {
    // Never throw into notification handler
  }
}

export function playFailureSound(): void {
  try {
    playTwoTone([196, 146.83], 350);
  } catch {
    // Never throw into notification handler
  }
}

/** Test-only: reset shared audio context between tests. */
export function __resetNotificationAudioForTest(): void {
  audioContext = null;
}
