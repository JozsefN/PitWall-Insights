import type { CarTelemetrySampleDto } from "../../data/contracts/sessions.contracts";

const HISTORY_MS = 10_000;
const MAX_SAMPLE_GAP_MS = 2_000;
const SPEED_SCALE_KPH = 400;

function afterTime(samples: readonly CarTelemetrySampleDto[], timeMs: number) {
  let low = 0;
  let high = samples.length;
  while (low < high) {
    const middle = (low + high) >>> 1;
    if (samples[middle].session_time_ms <= timeMs) low = middle + 1;
    else high = middle;
  }
  return low;
}

export function replayCardData(
  samples: readonly CarTelemetrySampleDto[],
  nowMs: number,
) {
  const end = afterTime(samples, nowMs);
  const last = samples[end - 1];
  const fromMs = nowMs - HISTORY_MS;
  const commands: string[] = [];
  let previous: number | undefined;
  for (let i = afterTime(samples, fromMs - 1); i < end; i++) {
    const { speed_kph: speed, session_time_ms: time } = samples[i];
    if (speed == null || !Number.isFinite(speed)) {
      previous = undefined;
      continue;
    }
    const x = ((time - fromMs) / HISTORY_MS) * 160;
    const y = 36 - Math.max(0, Math.min(1, speed / SPEED_SCALE_KPH)) * 32;
    const command =
      previous == null || time - previous > MAX_SAMPLE_GAP_MS ? "M" : "L";
    commands.push(`${command}${x.toFixed(2)} ${y.toFixed(2)}`);
    previous = time;
  }
  return {
    sample:
      last && nowMs - last.session_time_ms <= MAX_SAMPLE_GAP_MS
        ? last
        : undefined,
    hasPriorSample: Boolean(last),
    speedPath: commands.join(" "),
    hasSpeedTrace: commands.some((command) => command.startsWith("L")),
  };
}
