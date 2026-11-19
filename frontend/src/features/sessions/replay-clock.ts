// The moving markers subscribe to the fine clock. Controls and analysis use
// slower readouts so a frame never refreshes the whole workspace.
function createClockSignal() {
  let timeMs: number | null = null;
  const listeners = new Set<() => void>();
  return {
    getTime: () => timeMs,
    setTime(next: number) {
      if (timeMs === next) return;
      timeMs = next;
      listeners.forEach((listener) => listener());
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
  };
}

export function createReplayClock() {
  return { frame: createClockSignal(), readout: createClockSignal(), review: createClockSignal() };
}

export type ReplayClock = ReturnType<typeof createReplayClock>;
