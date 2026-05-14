import type { TrackStatusBand } from "../models";
import {
  formatTrackStatusDuration,
  formatTrackStatusRange,
} from "../utils/track-status";

type TrackStatusSummaryProps = {
  bands: TrackStatusBand[];
};

export function TrackStatusSummary({ bands }: TrackStatusSummaryProps) {
  if (bands.length === 0) {
    return null;
  }

  return (
    <div className="track-status-summary" aria-label="Track status ranges">
      {bands.slice(0, 6).map((band) => (
        <span
          key={band.key}
          className={`track-status-summary__chip track-status-summary__chip--${band.kind}`}
          title={buildBandTitle(band)}
        >
          <strong>{band.label}</strong>
          {formatTrackStatusRange(band)}
          <em>{formatTrackStatusDuration(band.durationMs)}</em>
        </span>
      ))}
      {bands.length > 6 ? (
        <span className="track-status-summary__chip track-status-summary__chip--more">
          +{bands.length - 6} more
        </span>
      ) : null}
    </div>
  );
}

function buildBandTitle(band: TrackStatusBand) {
  const source = band.source === "event" ? "status event timing" : "lap-level fallback";
  const message = band.message ? ` - ${band.message}` : "";
  return `${band.label} ${formatTrackStatusRange(band)} for ${formatTrackStatusDuration(band.durationMs)} (${source})${message}`;
}
