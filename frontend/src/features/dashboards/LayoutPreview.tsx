import { useMemo } from "react";
import type { DashboardConfig } from "../../widgets/registry/widget.types";
import { dashboardGrid } from "../../widgets/registry/widget.catalog";
import { WidgetBlueprint } from "../../widgets/shared/WidgetBlueprint";
import { draftFromLayout, GRID_GAP, GRID_ROW_HEIGHT } from "./editor-model";
import "./layout-preview.css";

type Props = { config: DashboardConfig; compact?: boolean; full?: boolean };

// One whole-dashboard drawing; editor overview and chooser cards use identical geometry.
export function LayoutPreview({
  config,
  compact = false,
  full = false,
}: Props) {
  const groups = useMemo(() => {
    const draft = draftFromLayout(
      {
        id: config.id,
        name: config.title ?? "Dashboard",
        source: "builtin",
        audience: "session-lookback",
        schemaVersion: 2,
        updatedAt: "",
        config,
      },
      false,
      false,
    );
    const measured = draft.sections.map((section, index) => {
      const heading = section.title ? 40 : draft.sections.length > 1 ? 30 : 0;
      const rows = Math.max(
        3,
        ...section.widgets.map(
          (widget) => widget.placement.y + widget.placement.h,
        ),
      );
      const height = rows * (GRID_ROW_HEIGHT + GRID_GAP) - GRID_GAP;
      return {
        ...section,
        heading,
        height,
        label: section.title || `Group ${index + 1}`,
      };
    });
    return measured.map((group, index) => ({
      ...group,
      top:
        16 +
        measured
          .slice(0, index)
          .reduce((sum, item) => sum + item.heading + item.height + 24, 0),
    }));
  }, [config]);
  const width = dashboardGrid.designWidth;
  const height = groups.length
    ? groups.at(-1)!.top + groups.at(-1)!.heading + groups.at(-1)!.height + 16
    : 240;
  return (
    <span
      className={`layout-preview${compact ? " layout-preview--compact" : ""}${full ? " layout-preview--full" : ""}`}
      style={full ? { aspectRatio: `${width} / ${height}` } : undefined}
    >
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMin meet"
        role={full ? "img" : undefined}
        aria-label={
          full
            ? "Whole dashboard preview. All groups appear in order; values are illustrative."
            : undefined
        }
        aria-hidden={full ? undefined : true}
      >
        <rect width={width} height={height} fill="#0d131e" />
        {groups.map((group) => (
          <g key={group.id} transform={`translate(0 ${group.top})`}>
            {group.heading ? (
              <text x="8" y="22" fill="#d7e5f7" fontSize="17" fontWeight="600">
                {group.label}
              </text>
            ) : null}
            {group.widgets.map((widget) => {
              const box = widget.placement;
              const x = box.x * ((width + GRID_GAP) / 12);
              const y = box.y * (GRID_ROW_HEIGHT + GRID_GAP) + group.heading;
              const w = box.w * ((width + GRID_GAP) / 12) - GRID_GAP;
              const h = box.h * (GRID_ROW_HEIGHT + GRID_GAP) - GRID_GAP;
              return (
                <svg
                  key={widget.instanceId}
                  aria-hidden="true"
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  viewBox={`0 0 ${w} ${h}`}
                >
                  <WidgetBlueprint
                    widgetId={widget.widgetId}
                    options={widget.options}
                    width={w}
                    height={h}
                  />
                </svg>
              );
            })}
          </g>
        ))}
      </svg>
    </span>
  );
}
