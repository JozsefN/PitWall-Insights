import type { GridPlacement } from "../../widgets/registry/widget.types";
import { widgetCatalog } from "../../widgets/registry/widget.catalog";
import type { EditorWidget } from "./editor-model";
import { TierBadge } from "./TierBadge";

type Props = {
  widget: EditorWidget;
  onPlace: (box: GridPlacement) => void;
  onOptions: (options: Record<string, unknown>) => void;
  onDuplicate: () => void;
};
export function PanelSettings({
  widget,
  onPlace,
  onOptions,
  onDuplicate,
}: Props) {
  const policy = widgetCatalog[widget.widgetId];
  const size = policy.sizing;
  return (
    <div className="editor-properties">
      <h3>
        Panel settings <TierBadge tier={policy.accessTier} />
      </h3>
      <p className="editor-size-rule">
        Minimum {size.minW} columns × {size.minH} rows.
        {size.minAspect
          ? ` Keep it wide: width must be at least ${size.minAspect} × height.`
          : " Flexible shape; content adapts to the available space."}{" "}
        Narrow panels use compact controls and content.
      </p>
      <label>
        Panel title
        <input
          maxLength={160}
          value={
            typeof widget.options?.title === "string"
              ? widget.options.title
              : ""
          }
          placeholder={policy.title}
          onChange={(event) => {
            const options = { ...widget.options };
            if (event.target.value) options.title = event.target.value;
            else delete options.title;
            onOptions(options);
          }}
        />
      </label>
      {(["x", "y", "w", "h"] as const).map((key) => (
        <label key={key}>
          {{ x: "Column", y: "Row", w: "Width", h: "Height" }[key]}
          <input
            type="number"
            aria-label={`Panel ${key}`}
            min={key === "w" ? size.minW : key === "h" ? size.minH : 0}
            max={
              key === "w"
                ? size.maxW
                : key === "h"
                  ? size.maxH
                  : key === "x"
                    ? 11
                    : 199
            }
            value={widget.placement[key]}
            onChange={(event) =>
              onPlace({
                ...widget.placement,
                [key]: Number(event.target.value),
              })
            }
          />
        </label>
      ))}
      {widget.widgetId === "telemetry-line-chart" ? (
        <label>
          Metric
          <select
            aria-label="Metric"
            value={String(widget.options?.metric ?? "speed_kph")}
            onChange={(event) => {
              const speed = event.target.value === "speed_kph";
              onOptions({
                ...widget.options,
                metric: event.target.value,
                metricLabel: speed ? "Speed" : "Throttle",
                unit: speed ? "kph" : "%",
              });
            }}
          >
            <option value="speed_kph">Speed</option>
            <option value="throttle_pct">Throttle</option>
          </select>
        </label>
      ) : null}
      <button className="button-secondary" type="button" onClick={onDuplicate}>
        Duplicate panel
      </button>
    </div>
  );
}
