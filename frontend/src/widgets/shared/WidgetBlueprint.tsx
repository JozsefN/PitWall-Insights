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
        fill="#151f2e"
        stroke="#40536c"
      />
      {header ? (
        <>
          <text
            x="16"
            y="27"
            fill="#e4edf9"
            fontSize={compact ? 13 : 16}
            fontWeight="600"
          >
            {title.length > (compact ? 26 : 48)
              ? title.slice(0, compact ? 25 : 47) + "…"
              : title}
          </text>
          {!compact ? (
            <text x="16" y="46" fill="#8fa3be" fontSize="10">
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
        {kind === "laps" ? (
          <>
            <rect width={contentWidth} height="26" rx="4" fill="#25364b" />
            {(compact
              ? ["DRV", "LAP", "TIME"]
              : ["DRIVER", "LAP", "TIME", "TYRE", "AGE"]
            ).map((label, index, labels) => (
              <text
                key={label}
                x={10 + (index * contentWidth) / labels.length}
                y="17"
                fill="#aebed4"
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
                  <text x="22" y="17" fill="#d0dced" fontSize="11">
                    {["DRV A", "DRV B", "DRV C"][index % 3]}
                  </text>
                  <text
                    x={contentWidth * (compact ? 0.38 : 0.24)}
                    y="17"
                    fill="#a9b9ce"
                    fontSize="11"
                  >
                    L{10 + index}
                  </text>
                  <text
                    x={contentWidth * (compact ? 0.65 : 0.44)}
                    y="17"
                    fill="#d0dced"
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
                        fill="#a9b9ce"
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
            <rect width={contentWidth} height="25" rx="4" fill="#23364c" />
            <text x="10" y="17" fill="#c6d7ec" fontSize="10">
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
                stroke="#384b61"
                strokeWidth="20"
                strokeLinejoin="round"
              />
              <path
                d="M55 160 35 110 95 74 143 88 194 45 271 32 345 75 326 111 286 110 267 160 211 182 140 144 115 185 55 160Z"
                fill="none"
                stroke="#7da5d2"
                strokeWidth="3"
              />
              {[
                [55, 160],
                [143, 88],
                [286, 110],
              ].map(([x, y], i) => (
                <g key={i}>
                  <circle cx={x} cy={y} r="6" fill={colors[i]} />
                  <text x={x + 10} y={y - 10} fill="#e3eaf4" fontSize="11">
                    DRV {String.fromCharCode(65 + i)}
                  </text>
                </g>
              ))}
            </svg>
            <text x="0" y={contentHeight - 3} fill="#8fa8c6" fontSize="10">
              {widgetId === "replay-track-map"
                ? "Replay clock · current positions"
                : "Position traces · circuit outline"}
            </text>
          </>
        ) : kind === "driver-cards" ? (
          <>
            {Array.from({ length: compact ? 2 : 3 }, (_, index) => {
              const n = compact ? 1 : 2;
              const cardW = (contentWidth - (n - 1) * 10) / n;
              const cardH = Math.max(
                75,
                Math.min(140, (contentHeight - 12) / 2),
              );
              return (
                <g
                  key={index}
                  transform={`translate(${(index % n) * (cardW + 10)} ${Math.floor(index / n) * (cardH + 10)})`}
                >
                  <rect
                    width={cardW}
                    height={cardH}
                    rx="7"
                    fill="#203249"
                    stroke={colors[index]}
                  />
                  <text x="12" y="24" fontSize="13" fill="#e0eafa">
                    DRV {String.fromCharCode(65 + index)}
                  </text>
                  <text x="12" y="50" fontSize="10" fill="#9cb4d2">
                    SPEED
                  </text>
                  <text x="12" y="72" fontSize="20" fill="#e0eafa">
                    2—8 <tspan fontSize="10">kph</tspan>
                  </text>
                  {cardW > 200 ? (
                    <>
                      <text x={cardW * 0.6} y="50" fontSize="10" fill="#9cb4d2">
                        GEAR
                      </text>
                      <text x={cardW * 0.6} y="72" fontSize="20" fill="#e0eafa">
                        7
                      </text>
                    </>
                  ) : null}
                  <rect
                    x="12"
                    y={cardH - 20}
                    width={cardW - 24}
                    height="5"
                    fill="#3a4d66"
                  />
                  <rect
                    x="12"
                    y={cardH - 20}
                    width={(cardW - 24) * 0.7}
                    height="5"
                    fill={colors[index]}
                  />
                </g>
              );
            })}
          </>
        ) : kind === "status" ? (
          <text x="12" y="30" fill="#a7b8cd" fontSize="12">
            Platform widget · unavailable in session layouts
          </text>
        ) : (
          <>
            <rect width={contentWidth} height="25" rx="4" fill="#203249" />
            <text x="10" y="17" fill="#b6c9e1" fontSize="10">
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
                <line key={y} x1="30" x2="490" y1={y} y2={y} stroke="#30435a" />
              ))}
              {[30, 140, 250, 360, 470].map((x) => (
                <line key={x} x1={x} x2={x} y1="5" y2="165" stroke="#26384e" />
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
            <text x="0" y={contentHeight - 3} fill="#8fa8c6" fontSize="10">
              {kind === "stints" || kind === "pace"
                ? "Lap number →"
                : "Session time →"}{" "}
              <tspan dx="16" fill="#61b6ff">
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
