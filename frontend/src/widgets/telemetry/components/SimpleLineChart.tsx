import { buildLinePath } from "../../../features/sessions/session-utils";
import { WidgetEmpty } from "../../shared/WidgetState";
import type { LineSeries } from "../models";

type SimpleLineChartProps = {
  series: LineSeries[];
  emptyMessage: string;
};

export function SimpleLineChart({ series, emptyMessage }: SimpleLineChartProps) {
  const activeSeries = series.filter((item) => item.points.length > 0);

  if (activeSeries.length === 0) {
    return <WidgetEmpty message={emptyMessage} />;
  }

  return (
    <div className="telemetry-chart">
      <div className="telemetry-chart__legend">
        {activeSeries.map((item) => (
          <span key={item.key} className="telemetry-driver-chip">
            <i style={{ backgroundColor: item.color }} />
            {item.label}
          </span>
        ))}
      </div>

      <svg viewBox="0 0 720 280" className="telemetry-chart__svg" preserveAspectRatio="none">
        <rect x="0" y="0" width="720" height="280" rx="18" className="telemetry-chart__bg" />
        {[48, 96, 144, 192, 240].map((y) => (
          <line key={y} x1="16" y1={y} x2="704" y2={y} className="telemetry-chart__grid" />
        ))}
        {activeSeries.map((item) => (
          <path
            key={item.key}
            d={buildLinePath(item.points, 720, 280)}
            fill="none"
            stroke={item.color}
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
      </svg>
    </div>
  );
}
