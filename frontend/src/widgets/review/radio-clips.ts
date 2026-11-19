import type { RadioClip } from "../../features/session-review/contracts";

export function radioClipsInWindow<Clip extends RadioClip>(clips: Clip[], window?: { startMs: number; timeMs: number }) {
  return window ? clips.filter((clip) =>
    clip.time_ms >= window.startMs && clip.time_ms <= window.timeMs && (clip.known_at_ms ?? clip.time_ms) <= window.timeMs,
  ) : clips;
}
