import { widgetCatalog } from "../registry/widget.catalog";
import type { WidgetId } from "../registry/widget.types";

type Props = {
  widgetId: WidgetId;
  width: number;
  height: number;
  options?: Record<string, unknown>;
  header?: boolean;
};
const colors = ["#61b6ff", "#e99c68", "#5dd5b0"];

// Deliberately illustrative. No hooks, session provider, network, or random data.
export function WidgetBlueprint({
  widgetId,
  width,
  height,
  options,
  header = true,
}: Props) {
  const policy = widgetCatalog[widgetId];
  const kind = policy?.previewKind ?? "status";
  const title =
    typeof options?.title === "string"
      ? options.title
      : (policy?.title ?? "Unavailable widget");
  const compact = width < (policy?.sizing.compactBelowPx ?? 420);
  const top = header ? (compact ? 48 : 62) : 12;
  const contentHeight = Math.max(40, height - top - 20);
  const contentWidth = Math.max(40, width - 32);
  const chartTop = compact ? 34 : 44;
  const chartHeight = Math.max(24, contentHeight - chartTop - 26);
  return (
    <svg
      className="widget-blueprint"
      data-preview-kind={kind}
      data-preview-mode={compact ? "compact" : "comfortable"}
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height="100%"
      aria-hidden="true"
    >
      <rect
        width={width}
        height={height}
        rx="10"
        fill="var(--color-bg-tertiary)"
        stroke="var(--color-border-strong)"
      />
      {header ? (
        <>
          <text
            x="16"
            y="27"
            fill="var(--color-text-primary)"
            fontSize={compact ? 13 : 16}
            fontWeight="600"
          >
            {title.length > (compact ? 26 : 48)
              ? title.slice(0, compact ? 25 : 47) + "…"
              : title}
          </text>
          {!compact ? (
            <text x="16" y="46" fill="var(--color-text-secondary)" fontSize="10">
              {kind === "track"
                ? "Circuit position and driver context"
                : kind === "laps"
                  ? "Lap-by-lap session detail"
                  : kind === "stints"
                    ? "Compound windows and pace"
                    : "Selected drivers · session context"}
            </text>
          ) : null}
        </>
      ) : null}
      <g transform={`translate(16 ${top})`}>
        {kind === "notifications" ? (
          <>
            {Array.from(
              {
                length: Math.max(
                  1,
                  Math.min(5, Math.floor(contentHeight / 66)),
                ),
              },
              (_, index) => (
                <g key={index} transform={`translate(0 ${index * 66})`}>
                  <rect
                    width={contentWidth}
                    height="57"
                    rx="6"
                    fill="var(--color-bg-tertiary)"
                  />
                  <rect width="3" height="57" rx="1" fill={colors[index % 3]} />
                  <text x="12" y="17" fill="var(--color-text-secondary)" fontSize="9">
                    REPORTED · RACE CONTROL
                  </text>
                  <text x="12" y="35" fill="var(--color-text-primary)" fontSize="11">
                    {
                      [
                        "Yellow flag · sector 2",
                        "DRV A · personal best",
                        "DRV B · pit visit",
                      ][index % 3]
                    }
                  </text>
                  <text x="12" y="48" fill="var(--color-text-secondary)" fontSize="8">
                    Illustrative message · expand for evidence
                  </text>
                </g>
              ),
            )}
          </>
        ) : kind === "tyre-timeline" ? (
          <>
            <text x="39" y="13" fill="var(--color-text-secondary)" fontSize="10">Lap</text>
            {["VER", "NOR", "LEC"].map((driver, index) => (
              <g key={driver} transform={`translate(0 ${25 + index * 27})`}>
                <text y="12" fill="var(--color-text-primary)" fontSize="9">{driver}</text>
                <rect x="38" width={Math.max(24, contentWidth - 40)} height="15" rx="4" fill="var(--color-control)" />
                <rect x="38" width={Math.max(10, (contentWidth - 40) * (.38 + index * .05))} height="15" rx="4" fill={index === 2 ? "#ef4444" : "#facc15"} />
                <rect x={38 + Math.max(10, (contentWidth - 40) * (.38 + index * .05))} width={Math.max(10, (contentWidth - 40) * .42)} height="15" rx="4" fill="#f8fafc" />
              </g>
            ))}
          </>
        ) : kind === "position-history" ? (
          <>
            <text y="12" fill="var(--color-text-secondary)" fontSize="9">P1</text>
            <text y={chartHeight - 8} fill="var(--color-text-secondary)" fontSize="9">P20</text>
            {[.2, .5, .8].map((row, index) => (
              <path key={row} d={`M24 ${chartHeight * row}h${(contentWidth - 25) * .27}v${(index % 2 ? 1 : -1) * chartHeight * .12}h${(contentWidth - 25) * .25}v${(index % 2 ? -1 : 1) * chartHeight * .22}H${contentWidth}`}
                stroke={colors[index]} strokeWidth="2" fill="none" />
            ))}
            <text x="24" y={chartHeight + 9} fill="var(--color-text-secondary)" fontSize="9">Completed lap</text>
          </>
        ) : kind === "insights" && (policy.previewDetail === "timing-bars" || policy.previewDetail === "delta-bars") ? (
          <>
            {(policy.previewLabels ?? []).slice(0, 4).map((label, index) => {
              const rowHeight = Math.min(34, contentHeight / 4);
              const start = Math.min(90, contentWidth * 0.35);
              const track = contentWidth - start - 7;
              const signed = policy.previewDetail === "delta-bars";
              const origin = signed ? track / 2 : 0;
              const point = signed ? track * (index % 2 ? 0.73 : 0.16) : track * (0.38 + (index % 3) * 0.28);
              return (
                <g key={label} transform={`translate(0 ${index * rowHeight})`}>
                  <text x="2" y="11" fill="var(--color-text-primary)" fontSize="8">{label}</text>
                  <rect x={start} y="5" width={track} height="7" rx="3.5" fill="var(--color-control)" />
                  {signed ? <path d={`M${start + origin} 3V14`} stroke="var(--color-border-strong)" /> : null}
                  <rect x={start + Math.min(origin, point)} y="7" width={Math.abs(point - origin)} height="3" rx="1.5" fill={colors[index % 3]} />
                  <circle cx={start + point} cy="8.5" r="4" fill={colors[index % 3]} />
                </g>
              );
            })}
          </>
        ) : kind === "insights" && policy.previewDetail === "lap-bars" ? (
          <>
            <text x="1" y="10" fill="var(--color-text-primary)" fontSize="9">Pace delta by lap</text>
            <path d={`M0 ${chartHeight + 17}H${contentWidth}`} stroke="var(--color-border-strong)" />
            {[.6, .42, .76, .31, .43, .08].map((fraction, index, bars) => {
              const barHeight = chartHeight * fraction;
              const widthPerBar = contentWidth / bars.length;
              const x = index * widthPerBar;
              return (
                <g key={index}>
                  <rect x={x + widthPerBar * 0.17} y={chartHeight + 17 - barHeight} width={widthPerBar * 0.66} height={barHeight} rx="3" fill={index === bars.length - 1 ? "var(--color-brand)" : "var(--color-focus)"} />
                  <text x={x + widthPerBar / 2} y={chartHeight + 30} textAnchor="middle" fill="var(--color-text-secondary)" fontSize="8">L{index + 12}</text>
                </g>
              );
            })}
          </>
        ) : kind === "insights" ? (
          <>
            {(
              policy.previewLabels ?? [
                "Reported context",
                "Calculated trend",
                "Scenario / index",
                "Evidence support",
              ]
            ).map((label, index) => {
              const x = (index % 2) * (contentWidth / 2 + 4),
                y = Math.floor(index / 2) * Math.min(78, contentHeight / 2);
              return (
                <g key={label} transform={`translate(${x} ${y})`}>
                  <rect
                    width={contentWidth / 2 - 5}
                    height={Math.min(69, contentHeight / 2 - 6)}
                    rx="6"
                    fill="var(--color-bg-tertiary)"
                    stroke="var(--color-border-strong)"
                  />
                  <text x="9" y="17" fill="var(--color-text-secondary)" fontSize="8">
                    {label}
                  </text>
                  {contentHeight > 100 ? (
                    <text x="9" y="39" fill={colors[index % 3]} fontSize="18">
                      {index % 2 ? "↗" : "—"}
                    </text>
                  ) : null}
                  {contentHeight > 120 ? (
                    <path
                      d={`M9 52h${Math.max(10, contentWidth / 2 - 30)}`}
                      stroke="var(--color-border-strong)"
                    />
                  ) : null}
                </g>
              );
            })}
            {contentHeight > 220 && policy.previewDetail ? (
              <g transform="translate(0 165)">
                {policy.previewDetail === "trend" ? (
                  <>
                    <path
                      d={`M0 25H${contentWidth}M0 60H${contentWidth}`}
                      stroke="var(--color-border-strong)"
                    />
                    <polyline
                      points={Array.from(
                        { length: 21 },
                        (_, i) =>
                          `${(i * contentWidth) / 20},${45 + Math.sin(i * 1.7) * 20}`,
                      ).join(" ")}
                      fill="none"
                      stroke="#5dd5b0"
                      strokeWidth="2"
                    />
                    <text y="80" fill="var(--color-text-secondary)" fontSize="9">
                      Trailing observations · time →
                    </text>
                  </>
                ) : policy.previewDetail === "table" ? (
                  <>
                    <rect
                      width={contentWidth}
                      height="23"
                      rx="3"
                      fill="var(--color-bg-tertiary)"
                    />
                    <text x="9" y="16" fill="var(--color-text-secondary)" fontSize="9">
                      DRIVER / EPISODE
                    </text>
                    <text
                      x={contentWidth * 0.6}
                      y="16"
                      fill="var(--color-text-secondary)"
                      fontSize="9"
                    >
                      COMPARISON
                    </text>
                    {[0, 1, 2].map((i) => (
                      <g key={i} transform={`translate(0 ${30 + i * 22})`}>
                        <path d={`M0 12H${contentWidth}`} stroke="var(--color-border-strong)" />
                        <text x="9" y="6" fill="var(--color-text-primary)" fontSize="9">
                          {["DRV A", "DRV B", "DRV C"][i]}
                        </text>
                        <path
                          d={`M${contentWidth * 0.6} 3h${contentWidth * 0.25}`}
                          stroke={colors[i]}
                        />
                      </g>
                    ))}
                  </>
                ) : null}
              </g>
            ) : null}
            <text x="2" y={contentHeight - 1} fill="var(--color-text-secondary)" fontSize="8">
              Illustrative structure · actual values need session data
            </text>
          </>
        ) : kind === "laps" ? (
          <>
            <rect width={contentWidth} height="26" rx="4" fill="var(--color-bg-tertiary)" />
            {(compact
              ? ["DRV", "LAP", "TIME"]
              : ["DRIVER", "LAP", "TIME", "TYRE", "AGE"]
            ).map((label, index, labels) => (
              <text
                key={label}
                x={10 + (index * contentWidth) / labels.length}
                y="17"
                fill="var(--color-text-secondary)"
                fontSize="10"
              >
                {label}
              </text>
            ))}
            {Array.from(
              { length: Math.max(1, Math.floor((contentHeight - 30) / 31)) },
              (_, index) => (
                <g key={index} transform={`translate(0 ${31 + index * 31})`}>
                  <rect
                    width={contentWidth}
                    height="26"
                    rx="4"
                    fill={index % 2 ? "#192638" : "#1e2e42"}
                  />
                  <circle cx="12" cy="13" r="3" fill={colors[index % 3]} />
                  <text x="22" y="17" fill="var(--color-text-primary)" fontSize="11">
                    {["DRV A", "DRV B", "DRV C"][index % 3]}
                  </text>
                  <text
                    x={contentWidth * (compact ? 0.38 : 0.24)}
                    y="17"
                    fill="var(--color-text-secondary)"
                    fontSize="11"
                  >
                    L{10 + index}
                  </text>
                  <text
                    x={contentWidth * (compact ? 0.65 : 0.44)}
                    y="17"
                    fill="var(--color-text-primary)"
                    fontSize="11"
                  >
                    1:2—.———
                  </text>
                  {!compact ? (
                    <>
                      <text
                        x={contentWidth * 0.64}
                        y="17"
                        fill="#dfb968"
                        fontSize="10"
                      >
                        MED
                      </text>
                      <text
                        x={contentWidth * 0.84}
                        y="17"
                        fill="var(--color-text-secondary)"
                        fontSize="11"
                      >
                        {index + 3}
                      </text>
                    </>
                  ) : null}
                </g>
              ),
            )}
          </>
        ) : kind === "track" ? (
          <>
            <rect width={contentWidth} height="25" rx="4" fill="var(--color-bg-tertiary)" />
            <text x="10" y="17" fill="var(--color-text-primary)" fontSize="10">
              {compact
                ? "Focus · Zoom · Reset"
                : "Follow selected drivers     Zoom −  +     Reset view"}
            </text>
            <svg
              x="0"
              y="33"
              width={contentWidth}
              height={Math.max(50, contentHeight - 57)}
              viewBox="0 0 400 220"
              preserveAspectRatio="xMidYMid meet"
            >
              <path
                d="M55 160 35 110 95 74 143 88 194 45 271 32 345 75 326 111 286 110 267 160 211 182 140 144 115 185 55 160Z"
                fill="none"
                stroke="var(--color-border-strong)"
                strokeWidth="20"
                strokeLinejoin="round"
              />
              <path
                d="M55 160 35 110 95 74 143 88 194 45 271 32 345 75 326 111 286 110 267 160 211 182 140 144 115 185 55 160Z"
                fill="none"
                stroke="var(--color-border-strong)"
                strokeWidth="3"
              />
              {[
                [55, 160],
                [143, 88],
                [286, 110],
              ].map(([x, y], i) => (
                <g key={i}>
                  <circle cx={x} cy={y} r="6" fill={colors[i]} />
                  <text x={x + 10} y={y - 10} fill="var(--color-text-primary)" fontSize="11">
                    DRV {String.fromCharCode(65 + i)}
                  </text>
                </g>
              ))}
            </svg>
            <text x="0" y={contentHeight - 3} fill="var(--color-text-secondary)" fontSize="10">
              {widgetId === "replay-track-map"
                ? "Replay clock · current positions"
                : "Position traces · circuit outline"}
            </text>
          </>
        ) : kind === "driver-cards" ? (
          <>
            {(compact ? [0] : [0, 1]).map((index) => {
              const cardWidth = compact ? contentWidth : (contentWidth - 8) / 2;
              const cardHeight = Math.min(Math.max(88, contentHeight), 132);
              const qualifying = widgetId === "lookback-driver-cards";
              return (
                <g key={index} transform={`translate(${index * (cardWidth + 8)} 0)`}>
                  <rect width={cardWidth} height={cardHeight} rx="8" fill="var(--color-recessed)" stroke="var(--color-border-strong)" />
                  <rect width="3" height={cardHeight} rx="1.5" fill={colors[index]} />
                  <rect x="4" width={cardWidth - 5} height="35" rx="5" fill="var(--color-selection)" />
                  <text x={cardWidth - 9} y="31" textAnchor="end" fill={colors[index]} opacity=".6" fontSize="27" fontWeight="800">{index ? "4" : "1"}</text>
                  <text x="12" y="23" fill="var(--color-text-primary)" fontSize="12">{index ? "NOR" : "VER"}</text>
                  <text x="12" y="54" fill="var(--color-text-primary)" fontSize="12">{qualifying ? "Q3   1:16.871" : "284 km/h"}</text>
                  <polyline points={`12,72 ${cardWidth * .28},67 ${cardWidth * .47},73 ${cardWidth * .66},62 ${cardWidth - 12},65`}
                    fill="none" stroke={colors[index]} strokeWidth="2" />
                  <rect x="12" y={cardHeight - 9} width={(cardWidth - 24) * .68} height="4" rx="2" fill={qualifying ? "#6de5ac" : colors[index]} />
                </g>
              );
            })}
          </>
        ) : kind === "status" ? (
          <text x="12" y="30" fill="var(--color-text-secondary)" fontSize="12">
            Platform widget · unavailable in session layouts
          </text>
        ) : (
          <>
            <rect width={contentWidth} height="25" rx="4" fill="var(--color-bg-tertiary)" />
            <text x="10" y="17" fill="var(--color-text-secondary)" fontSize="10">
              {kind === "stints"
                ? compact
                  ? "Tyre · clean laps"
                  : "Tyre compound    Clean laps    Outliers    Trend"
                : kind === "brake"
                  ? "Brake ON / OFF · selected lap"
                  : `${options?.metric === "throttle_pct" ? "Throttle %" : kind === "pace" ? "Lap time" : "Speed kph"} · ${compact ? "clean laps" : "selected drivers    Reference    Clean laps"}`}
            </text>
            <svg
              x="0"
              y={chartTop}
              width={contentWidth}
              height={chartHeight}
              viewBox="0 0 500 180"
              preserveAspectRatio="none"
            >
              {[30, 70, 110, 150].map((y) => (
                <line key={y} x1="30" x2="490" y1={y} y2={y} stroke="var(--color-border-strong)" />
              ))}
              {[30, 140, 250, 360, 470].map((x) => (
                <line key={x} x1={x} x2={x} y1="5" y2="165" stroke="var(--color-border-strong)" />
              ))}
              {kind === "stints" ? (
                <>
                  {[0, 1, 2].map((i) => (
                    <g key={i}>
                      <rect
                        x={35 + i * 14}
                        y={25 + i * 42}
                        width={160 - i * 16}
                        height="18"
                        rx="4"
                        fill={["#a85e60", "#bf9f51", "#6b98bc"][i]}
                      />
                      <rect
                        x={210 + i * 10}
                        y={25 + i * 42}
                        width={240 - i * 25}
                        height="18"
                        rx="4"
                        fill={["#bf9f51", "#6b98bc", "#a85e60"][i]}
                      />
                      <path
                        d={`M35 ${52 + i * 42}L120 ${42 + i * 42}L210 ${48 + i * 42}L320 ${36 + i * 42}L450 ${32 + i * 42}`}
                        fill="none"
                        stroke={colors[i]}
                        strokeWidth="2"
                      />
                    </g>
                  ))}
                </>
              ) : kind === "brake" ? (
                <>
                  {colors.slice(0, 2).map((color, i) => (
                    <path
                      key={color}
                      d={`M30 ${145 - i * 42}H90V${30 + i * 34}H150V${145 - i * 42}H235V${30 + i * 34}H290V${145 - i * 42}H360V${30 + i * 34}H415V${145 - i * 42}H490`}
                      fill="none"
                      stroke={color}
                      strokeWidth="3"
                    />
                  ))}
                </>
              ) : (
                colors
                  .slice(0, 2)
                  .map((color, i) => (
                    <path
                      key={color}
                      d={
                        i
                          ? "M30 140L65 132L95 145L140 62L190 89L235 50L285 110L335 80L385 102L440 40L490 59"
                          : "M30 125L65 114L95 132L140 35L190 65L235 30L285 90L335 62L385 80L440 18L490 30"
                      }
                      fill="none"
                      stroke={color}
                      strokeWidth="3"
                    />
                  ))
              )}
            </svg>
            <text x="0" y={contentHeight - 3} fill="var(--color-text-secondary)" fontSize="10">
              {kind === "stints" || kind === "pace"
                ? "Lap number →"
                : "Session time →"}{" "}
              <tspan dx="16" fill="var(--color-text-secondary)">
                ● DRV A
              </tspan>
              <tspan dx="12" fill="#e99c68">
                ● DRV B
              </tspan>
            </text>
          </>
        )}
      </g>
    </svg>
  );
}
