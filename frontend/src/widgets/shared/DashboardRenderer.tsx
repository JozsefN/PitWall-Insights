import type { CSSProperties } from "react";
import { ResponsiveWidgetFrame } from "./ResponsiveWidgetFrame";
import { widgetRegistry } from "../registry/widget.registry";
import { dashboardGrid } from "../registry/widget.catalog";
import type {
  DashboardConfig,
  DashboardSection,
  HeightMode,
  SectionLayoutNode,
  LayoutGroupNode,
  LayoutWidgetNode,
} from "../registry/widget.types";
import { WidgetCard } from "./WidgetCard";
import { WidgetError } from "./WidgetState";
import "./dashboard-renderer.css";
import "./widget-responsive.css";

const legacyHeights: Partial<Record<HeightMode, number>> = {
  sm: 140,
  md: 240,
  lg: 320,
};

type DashboardRendererProps = {
  config: DashboardConfig;
};

export function DashboardRenderer({ config }: DashboardRendererProps) {
  return (
    <div className="dashboard">
      {(config.title || config.subtitle) && (
        <header className="dashboard__hero">
          <div>
            {config.title ? (
              <h1 className="dashboard__title">{config.title}</h1>
            ) : null}
            {config.subtitle ? (
              <p className="dashboard__subtitle">{config.subtitle}</p>
            ) : null}
          </div>
        </header>
      )}

      <div className="dashboard__sections">
        {config.sections.map((section) => (
          <DashboardSectionView key={section.id} section={section} />
        ))}
      </div>
    </div>
  );
}

function DashboardSectionView({ section }: { section: DashboardSection }) {
  return (
    <section className="dashboard-section">
      {(section.title || section.description) && (
        <div className="dashboard-section__header">
          {section.title ? (
            <h2 className="dashboard-section__title">{section.title}</h2>
          ) : null}
          {section.description ? (
            <p className="dashboard-section__description">
              {section.description}
            </p>
          ) : null}
        </div>
      )}

      <div className="dashboard-section__body">
        <LayoutNodeRenderer node={section.layout} />
      </div>
    </section>
  );
}

function LayoutNodeRenderer({
  node,
  panelHeight,
}: {
  node: SectionLayoutNode;
  panelHeight?: number;
}) {
  if (node.type === "group") {
    return <LayoutGroupRenderer node={node} />;
  }

  return <LayoutWidgetRenderer node={node} panelHeight={panelHeight} />;
}

function LayoutGroupRenderer({ node }: { node: LayoutGroupNode }) {
  const gap = node.gap ?? 16;
  return (
    <div
      className={`layout-group layout-group--${node.grid ? "grid" : node.direction}`}
      style={{
        gap,
        gridTemplateColumns: node.grid
          ? `repeat(${node.grid.columns}, minmax(0, 1fr))`
          : undefined,
        gridAutoRows: node.grid?.rowHeight,
      }}
    >
      {node.children.map((child, index) => (
        <LayoutNodeRenderer
          key={index}
          node={child}
          panelHeight={
            node.grid && child.type === "widget" && child.placement
              ? child.placement.h * (node.grid.rowHeight + gap) - gap
              : undefined
          }
        />
      ))}
    </div>
  );
}

function LayoutWidgetRenderer({
  node,
  panelHeight,
}: {
  node: LayoutWidgetNode;
  panelHeight?: number;
}) {
  const definition = widgetRegistry[node.widgetId];
  const Component = definition?.component;
  const defaultRows = definition?.sizing.defaultH ?? 5;
  const catalogHeight =
    defaultRows * (dashboardGrid.rowHeight + dashboardGrid.gap) -
    dashboardGrid.gap;
  const legacyMinimum = node.minHeight ?? 0;
  const legacyPreferred =
    legacyMinimum || (legacyHeights[node.height ?? "auto"] ?? catalogHeight);
  const height =
    panelHeight ??
    Math.max(
      legacyMinimum,
      Math.min(legacyPreferred, node.maxHeight ?? Infinity),
    );

  return (
    <div
      className={[
        "layout-widget",
        `layout-widget--width-${sanitizeClassToken(node.width ?? "fill")}`,
        node.className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={
        {
          "--panel-height": `${height}px`,
          flexGrow: node.grow,
          gridColumn: node.placement
            ? `${node.placement.x + 1} / span ${node.placement.w}`
            : undefined,
          gridRow: node.placement
            ? `${node.placement.y + 1} / span ${node.placement.h}`
            : undefined,
        } as CSSProperties
      }
    >
      {Component ? (
        <ResponsiveWidgetFrame widgetId={node.widgetId}>
          <Component options={node.options} />
        </ResponsiveWidgetFrame>
      ) : (
        <WidgetCard
          title="Unavailable Widget"
          description={`The widget "${node.widgetId}" is not registered in this build.`}
        >
          <WidgetError />
        </WidgetCard>
      )}
    </div>
  );
}

function sanitizeClassToken(value: string) {
  return value.replace(/\//g, "-");
}
