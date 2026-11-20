import type { GridPlacement } from "../../widgets/registry/widget.types";
import { widgetCatalog } from "../../widgets/registry/widget.catalog";
import type { EditorWidget } from "./editor-model";
import { TierBadge } from "./TierBadge";
import { Availability } from "./Availability";
import { eventLabels } from "../race-insights/contracts";
import { defaultEventTypes, reportedEventTypes } from "../race-insights/presentation";
import { insightPanels } from "../../widgets/insights/panel-specs";
import { resolveTrackMapLayer, trackMapLayers } from "../../widgets/track-map/models";

type Props = {
  widget: EditorWidget;
  modelAccess: boolean;
  onPlace: (box: GridPlacement) => void;
  onOptions: (options: Record<string, unknown>) => void;
  onDuplicate: () => void;
};
export function PanelSettings({
  widget,
  modelAccess,
  onPlace,
  onOptions,
  onDuplicate,
}: Props) {
  const policy = widgetCatalog[widget.widgetId];
  const size = policy.sizing;
  const layeredMap =
    widget.widgetId === "replay-track-map" ||
    widget.widgetId === "session-track-map";
  return (
    <div className="editor-properties">
      <h3>
        Panel settings <TierBadge tier={policy.accessTier} />
      </h3>
      <Availability
        modes={policy.supportedAudiences}
        kinds={policy.sessionKinds ?? []}
      />
      <p>{policy.availabilityNote}</p>
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
      {widget.widgetId in insightPanels &&
      widget.widgetId !== "race-notifications" ? (
        <>
          <label>
            <input
              type="checkbox"
              checked={widget.options?.showSupport !== false}
              onChange={(event) =>
                onOptions({
                  ...widget.options,
                  showSupport: event.target.checked,
                })
              }
            />{" "}
            Show evidence support
          </label>
          <label>
            <input
              type="checkbox"
              checked={widget.options?.showRanges !== false}
              onChange={(event) =>
                onOptions({
                  ...widget.options,
                  showRanges: event.target.checked,
                })
              }
            />{" "}
            Show sensitivity ranges
          </label>
        </>
      ) : null}
      {widget.widgetId === "race-notifications" ? (
        <>
          <label>
            Messages shown
            <select
              aria-label="Messages shown"
              value={String(widget.options?.maxItems ?? "auto")}
              onChange={(event) =>
                onOptions({
                  ...widget.options,
                  maxItems:
                    event.target.value === "auto"
                      ? "auto"
                      : Number(event.target.value),
                })
              }
            >
              <option value="auto">Fit panel height</option>
              <option value="3">Latest 3</option>
              <option value="5">Latest 5</option>
              <option value="10">Latest 10</option>
            </select>
          </label>
          <label>
            Driver scope
            <select
              aria-label="Notification driver scope"
              value={String(widget.options?.driverScope ?? "all")}
              onChange={(event) =>
                onOptions({
                  ...widget.options,
                  driverScope: event.target.value,
                })
              }
            >
              <option value="all">Entire field</option>
              <option value="selected">Selected drivers + race control</option>
            </select>
          </label>
          <label>
            Minimum severity
            <select
              value={String(widget.options?.minSeverity ?? "info")}
              onChange={(event) =>
                onOptions({
                  ...widget.options,
                  minSeverity: event.target.value,
                })
              }
            >
              <option value="info">All messages</option>
              <option value="watch">Watch + warnings</option>
              <option value="warning">Warnings only</option>
            </select>
          </label>
          <label>
            Trailing window
            <select
              value={String(widget.options?.lookbackMinutes ?? 5)}
              onChange={(event) =>
                onOptions({
                  ...widget.options,
                  lookbackMinutes: Number(event.target.value),
                })
              }
            >
              <option value="1">1 minute</option>
              <option value="3">3 minutes</option>
              <option value="5">5 minutes</option>
            </select>
          </label>
          <fieldset className="editor-event-options">
            <legend>Notification categories</legend>
            {modelAccess ? <label>
              <input
                type="checkbox"
                checked={widget.options?.includeCandidates === true}
                onChange={(event) =>
                  onOptions({
                    ...widget.options,
                    includeCandidates: event.target.checked,
                  })
                }
              />{" "}
              Include model detections (unconfirmed)
            </label> : null}
            {(modelAccess ? defaultEventTypes : reportedEventTypes).map((kind) => {
              const selected = Array.isArray(widget.options?.eventTypes)
                ? (widget.options.eventTypes as string[])
                : defaultEventTypes;
              return (
                <label key={kind}>
                  <input
                    type="checkbox"
                    checked={selected.includes(kind)}
                    onChange={(event) =>
                      onOptions({
                        ...widget.options,
                        eventTypes: event.target.checked
                          ? [...selected, kind]
                          : selected.filter((item) => item !== kind),
                      })
                    }
                  />
                  {eventLabels[kind]}
                </label>
              );
            })}
          </fieldset>
        </>
      ) : null}
      {layeredMap ? (
        <label>
          Default map layer
          <select
            aria-label="Default map layer"
            value={resolveTrackMapLayer(widget.options?.mapLayer)}
            onChange={(event) =>
              onOptions({ ...widget.options, mapLayer: event.target.value })
            }
          >
            {Object.entries(trackMapLayers).map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {layeredMap || widget.widgetId === "track-surface" ? (
        <label>
          Registered track context ID
          <input
            maxLength={64}
            value={String(widget.options?.contextId ?? "")}
            onChange={(event) =>
              onOptions({
                ...widget.options,
                contextId: event.target.value.trim(),
              })
            }
            placeholder="Saved strategy context"
          />
        </label>
      ) : null}
      <button className="button-secondary" type="button" onClick={onDuplicate}>
        Duplicate panel
      </button>
    </div>
  );
}
